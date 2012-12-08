from django import template
from django import forms
from django.http import HttpResponseRedirect

from pirate_forum.models import ForumDimension, DimensionTracker

from search.core import search
from oa_cache.models import ListCache
from django.template import Context, Template

import datetime
import pytz

from django.shortcuts import redirect

from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from django.core.cache import cache as memcache

from pirate_core.middleware import TYPE_KEY, OBJ_KEY, DIM_KEY, START_KEY, END_KEY, PHASE_KEY

from pirate_ranking.models import get_ranked_list
from pirate_sources.models import URLSource

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from pirate_core import HttpRedirectException, namespace_get
from pirate_consensus.models import UpDownVote, Consensus, Phase, PhaseLink
from pirate_consensus.tasks import initiate_nextphase, local_tz_to_utc

from pirate_reputation.models import ReputationDimension
from pirate_forum.models import ForumBlob, Question, Edit, Search
from pirate_forum.models import  BlobEditForm, View
from pirate_forum.tasks import create_edit
from pirate_core.forms import ComboFormFactory
from pirate_topics.models import Topic, MyGroup
from pirate_topics.forms import TopicForm

from pirate_profile.models import Profile

from django.utils.html import urlize

from pirate_signals.models import aso_rep_event, update_agent

from pirate_badges.models import check_badges

from customtags.decorators import block_decorator
register = template.Library()
block = block_decorator(register)

# this function assignment lets us reuse the same code block a bunch of places
get_namespace = namespace_get('pp_blob')


def get_form(t):
    #grabs the appropriate form for the text input corresponding to type from TYPE_CHOICES
    fd = ForumDimension.objects.get(key=t)
    return fd.get_form(), fd.get_model(), fd.name


def get_models():
    #returns a list of child models for ForumBlob
    return ForumDimension.objects.filter(is_content=True)


@register.filter    
def subtract(value, arg):
    return value - int(arg)


@block
def pp_if_forum_blob(context, nodelist, *args, **kwargs):
    """Retrieves blob help text."""
    context.push()
    namespace = get_namespace(context)

    obj = kwargs.pop('object',  None)
    try:
        obj.get_blob_key()
        namespace['is_blob'] = True
    except:
        namespace['is_blob'] = False
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_blob_help_text(context, nodelist, *args, **kwargs):
    """Retrieves blob help text."""
    context.push()
    namespace = get_namespace(context)

    t = kwargs.pop('dimension', None)

    try:
        fd = ForumDimension.objects.get(key=t)
        namespace['help_text'] = fd.help_text
    except:
        namespace['help_text'] = "KeyError: < " + str(t) + " >Help Text"
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_blob_dim_readable(context, nodelist, *args, **kwargs):
    """Retrieves blob dimension in human readable format."""
    context.push()
    namespace = get_namespace(context)

    t = kwargs.pop('dimension', None)
    try:
        f = get_form(t)[2]
    except:
        f = 'Error: Human Readable Dimension Not Found'

    namespace['dim_human_readable'] = f

    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_questions(context, nodelist, *args, **kwargs):
    """Retrieves blob dimension in human readable format."""
    context.push()
    namespace = get_namespace(context)

    phase = kwargs.pop('phase', None)
    parent = kwargs.pop('object', None)
    start = kwargs.pop('start', None)
    end = kwargs.pop('end', None)
    key = kwargs.pop('key', None)
    dimension = kwargs.pop('dimension', None)

    if isinstance(start, int) and isinstance(end, int):
        try:
            start, end = (int(start), int(end))
        except:
            raise ValueError("The argument 'start=' and 'end=' to the pp_get_blob_list tag must be "
                                 "provided in the form of an int")
    else:
        start, end = (0, 20)

    if dimension is None:
        raise ValueError("The argument 'dimension=' to the pp_get_blob_list tag must be "
                                 "provided in the form of an string")

    if key is None:
        if parent is None:
            key = '/p/list/' + '/' + START_KEY + str(start) + '/' + END_KEY + str(end) + '/' + DIM_KEY + str(dimension)
        else:
            ctype = ContentType.objects.get_for_model(parent)
            key = '/p/list/' + TYPE_KEY + str(ctype.pk) + '/' + OBJ_KEY + str(parent.pk) + '/' + START_KEY + str(start) + '/' + END_KEY + str(end) + '/' + DIM_KEY + str(dimension)
        #if phase is not None:
        #    key += '/' + PHASE_KEY + str(phase)
    l = ListCache.objects.get(content_type='proposals', template='issues')

    cached_list, tot_items = l.get_or_create_list(key, {}, forcerender=True)

    namespace['count'] = tot_items
    namespace['key'] = key
    namespace['blob_list'] = cached_list

    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_blob_subcontext(context, nodelist, *args, **kwargs):
    """
       This method receives a dimension and object, then parses that for the following
       special cases where dimensions do not provide enough context to the submit.html
       template. 
            *Subtypes: For instance the argument blob has subtypes of Stance. 
                       The specified stance can then be by supplying the 
                       object with the id of that stance. Then the blob form is 
                       aware of the type that should be specifed, so it is not
                       manually necessary for the user to enter stance type.

       THis allows the template author to specify Stance with the dimension, thus
       allowing for links to create preloaded content, for instance "Submit Nay Argument".
       *This template tag must encompass the pp_blob form tag.
    """

    context.push()
    namespace = get_namespace(context)

    dimension = kwargs.pop('dimension', None)

    #ARGUMENT SUBTYPES
    if dimension == 'yea':
        arg, created = Stance.objects.get_or_create(arg="yea")
        namespace['dimension'] = 'arg'
        namespace['sub'] = {'stance': arg}

    elif dimension == 'nay':
        arg, created = Stance.objects.get_or_create(arg="nay")
        namespace['dimension'] = 'arg'
        namespace['sub'] = {'stance': arg}
    else:
        namespace['dimension'] = dimension
        namespace['sub'] = {}

    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_check_codes(context, nodelist, *args, **kwargs):
    context.push()
    namespace = get_namespace(context)
    codes = memcache.get("rank_update_codes")
    cached_list = []
    if codes is not None:
        for i in codes.keys():
            cached_list.append(str(i) + ':' + str(memcache.get(i)))
        namespace['cache'] = cached_list

    namespace['codes'] = codes
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_blob_list(context, nodelist, *args, **kwargs):
    """
    These tests are deprecated.

    return output will optionally look for a topic or a
    rng of items in order to further refine the list.

    *Possible Dimension Arguments:
        ** hot: highly intereresting articles based on issue.interest
        ** new: latest content based on submit date
        ** top: those with the most votes
        ** cont: controversial issues that have the userbased divided
        ** numc: Ranked by number of commefrom pirate_issues.models import Topic, Issue, Rankingnts

    The default dimension is "new" when no dimension is specified.

    In order to generate a url that will provide rng information to this tag via
    request.rng, use a url tag of the following form:

    {% url pp-page template="filename.html" start=0 end=20 %}

    In this way, the tag can be invoked as follows:

    {% pp-issue-list topic=topic rng=request.rng dimension="dim" %}
       Do stuff with {{ pp-issue.issue_list }}
    {% endpp-issue-list %}
    """
    context.push()
    namespace = get_namespace(context)

    #user  = kwargs.pop('user',  None)
    parent = kwargs.pop('object', None)
    start = kwargs.pop('start', None)
    end = kwargs.pop('end', None)
    key = kwargs.pop('key', None)
    dimension = kwargs.pop('dimension', None)
    child = kwargs.pop('child', None)

    if isinstance(start, int) and isinstance(end, int):
        try:
            start, end = (int(start), int(end))
        except:
            raise ValueError("The argument 'start=' and 'end=' to the pp_get_blob_list tag must be "
                                 "provided in the form of an int")
    else:
        start, end = (0, 20)

    if dimension is None:
        raise ValueError("The argument 'dimension=' to the pp_get_blob_list tag must be "
                                 "provided in the form of an string")

    if key is None:
        if parent is None:
            key = 'list/' + '/-s' + str(start) + '/-e' + str(end) + '/-d' + str(dimension)
        else:
            ctype = ContentType.objects.get_for_model(parent)
            key = 'list/-t' + str(ctype.pk) + '/-o' + str(parent.pk) + '/-s' + str(start) + '/-e' + str(end) + '/-d' + str(dimension)

    l = ListCache.objects.get(content_type='item', template="children")

    cached_list, tot_items = l.get_or_create_list(key, {}, forcerender=False)

    namespace['count'] = tot_items
    namespace['blob_list'] = cached_list
    namespace['cached'] = False

    #else:
    #    namespace['count'] = cached_list[1]
    #    namespace['blob_list'] = cached_list[0]
    #    namespace['cached'] = True

    #issue list must be empty
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_forumdimension(context, nodelist, *args, **kwargs):
    '''
    Returns a ForumDimension object with key=dimension
    '''
    context.push()
    namespace = get_namespace(context)

    dimension = kwargs.get('dimension', None)
    try:
        fd = ForumDimension.objects.get(key=dimension)
    except:
        fd = None

    namespace['forumdimension'] = fd

    output = nodelist.render(context)
    context.pop()

    return output


class TypeForm(forms.Form):
    ctype = forms.ModelChoiceField(label=(u'Content Type'),
        queryset=ForumDimension.objects.filter(is_content=True).exclude(is_child=True))


###SOME HELPER FUNCTIONS THAT ARE DEFERRED FOR PP_BLOB_FORM
def defer_dimensiontracker_update(parent, dimension):
    try:
        fd = ForumDimension.objects.get(key=dimension)
        d, is_new = DimensionTracker.objects.get_or_create(object_pk=parent.pk, dimension=fd)
        if is_new:
            d.children = 1
            usc = UserSaltCache(div_id='#sort')
            for ranking_dim in ('hn', 'h', 'n', 'c'):
                context = {'dimension': ranking_dim, 'object': parent, 'sort_type': dimension}
                usc.render(context, forcerender=True)
        else:
            d.children = d.children + 1
        d.save()
    except:
        pass
        #forumdimension doesn't work


@block
def pp_blob_form(context, nodelist, *args, **kwargs):
    '''form_id = forms.CharField(widget=forms.HiddenInput(), initial="pp-issue-form")
    This block tag can create or process forms either to create or to modify issues.
    Usage is as follows:

    {% pp_blob_form POST=request.POST path=request.path parent=request.object %}
       Do stuff with {{ pp-issue.form }}.
    {% endpp_blob_form %}

    This form has become a little overloaded.

    '''
    context.push()
    namespace = get_namespace(context)

    POST = kwargs.get('POST', None)
    parent = kwargs.get('parent', None)
    user = kwargs.get('user', None)
    dimension = kwargs.get('dimension', None)
    obj = kwargs.get('object', None)
    edit = kwargs.get('edit', None)
    #subcontext imparted to form
    namespace['timezones'] = pytz.common_timezones

    #for editting objects
    if edit and obj is not None:
        blob_form, model, verbose_name = get_form(dimension)
        blob_form = BlobEditForm
        if POST:
            #save editted form
            form = blob_form(POST, auto_id='id_for_%s_' + str(obj.pk), prefix=user.username)
            #get info for diff
            old_text = obj.description
            if form.is_valid():
                #blob = form.save(commit=False)
                obj.description = form.cleaned_data['description']
                obj.summary = form.cleaned_data['summary']
                #blob.description = urlize(blob.description, trim_url_limit=30, nofollow=True)
                obj.save()
                new_text = form.cleaned_data['description']

                #create edit
                ctype = ContentType.objects.get_for_model(obj)

                #compute diff using diff_match_patch from google

                create_edit.apply_async(args=[obj.pk, user.pk, ctype.pk, new_text, old_text])
                namespace['form_complete'] = True
                namespace['path'] = obj
                namespace['form'] = form
            else:
                namespace['errors'] = form.errors
                namespace['form'] = form

        else:
            form = blob_form(initial={'summary': obj.summary, 'description': obj.description}, prefix=user.username, auto_id='id_for_%s_' + str(obj.pk))
            namespace['form'] = form

    elif dimension is not None:
        if isinstance(parent, unicode):
            parent = None
        elif parent is not None:
            if ContentType.objects.get_for_model(parent) == ContentType.objects.get_for_model(User):
                parent = None
        blob_form, model, verbose_name = get_form(dimension)
        fd = ForumDimension.objects.get(key=dimension)
        #get appropriate form

        if POST and user is not None:
            comboform = ComboFormFactory(TopicForm(POST), blob_form(POST)).ComboForm()
            namespace['form'] = comboform
            for form in comboform._forms:
                if form.is_valid():
                    #if this is a TopicForm, we must extract the parent
                    if 'group' in form.cleaned_data:
                        try:
                            parent = Topic.objects.get(summary=form.cleaned_data['group'])
                            cnt = MyGroup.objects.filter(topic=parent, user=user)
                            if cnt == 0:
                                namespace['grouperrors'] = 'You are not a member of that Group.'
                                output = nodelist.render(context)
                                context.pop()
                                return output
                        except:
                            namespace['grouperrors'] = 'This Group does not exist.'
                            output = nodelist.render(context)
                            context.pop()
                            return output

                    else:
                        #blob form
                        if parent is not None:
                            parent.children += 1
                            parent.save()
                        blob = form.save(commit=False)
                        blob.forumdimension = fd
                        blob.user = user
                        blob.description = form.cleaned_data['blobdescription']
                        #blob.description = urlize(blob.description, trim_url_limit=30, nofollow=True)
                        blob.parent_pk = parent.pk
                        blob.parent_type = ContentType.objects.get_for_model(parent)
                        ctype = ContentType.objects.get_for_model(Topic)
                        if blob.parent_type != ctype:
                            parent.parent.solutions += 1
                            parent.parent.save()
                            #####relevant to VOTING and TIME
                            now = datetime.datetime.now()
                            now = now.replace(tzinfo=pytz.utc)
                        blob.save()

                        contype = ContentType.objects.get_for_model(blob.__class__)

                        #CONSENSUS RELATED DENORMALIZATION
                        # All ForumBlobs have consensus objects attached
                        try:
                            parent_cons = Consensus.objects.get(object_pk=parent.pk)
                            if parent_cons.child_vote_type != None:
                                cvt = parent_cons.child_vote_type
                            else:
                                cvt = ContentType.objects.get_for_model(UpDownVote)
                        except:
                            cvt = ContentType.objects.get_for_model(UpDownVote)
                        cons, is_new = Consensus.objects.get_or_create(content_type=contype,
                                    object_pk=blob.pk,
                                    vote_type=cvt,
                                    parent_pk=blob.parent_pk)

                        if is_new:
                            cons.intiate_vote_distributions()
                            #deprecated but lets holdon to phases for now
                            cons.phasename = "temp"
                            cons.save()

                        aso_rep_event.send(sender=user, event_score=1, user=user, initiator=user, dimension=ReputationDimension.objects.get(name=blob.get_verbose_name()), related_object=cons)
                        update_agent.send(sender=blob, type="content", params=[ContentType.objects.get_for_model(blob.__class__).app_label, verbose_name.lower(), blob.pk])
                        #check badges for this model on creation
                        check_badges(user, model, user)

                        #update the dimensiontracker, used for sorting by content type
                        #deferred.defer(defer_dimensiontracker_update, parent, dimension)

                        #if is_new: #if this is a new issue/consensus, send signal for reputation
                        #relationship_event.send(sender=issue,obj=issue,parent=issue.topic)
                        namespace['path'] = blob
                        namespace['form_complete'] = True
                        #provide context with extension path
                        #raise HttpRedirectException(HttpResponseRedirect(path))

                else:
                    namespace['errors'] = form.errors
                    output = nodelist.render(context)
                    context.pop()
                    return output
        else:
            blob_form, model, verbose_name = get_form(dimension)
            if parent is not None:
                form = ComboFormFactory(TopicForm(auto_id='id_for_%s_' + str(parent.pk), initial={'group': str(parent.summary)}), blob_form()).ComboForm()
            else:
                form = ComboFormFactory(TopicForm(), blob_form()).ComboForm()
            namespace['form'] = form

        namespace['POST'] = POST, parent

        #try to set ids for side effects
        try:
            namespace['object'] = cons
            namespace['object_pk'] = blob.pk
            ctype = ContentType.objects.get_for_model(blob)
            namespace['content_type'] = ctype.pk
        except:
             pass

    if parent is not None:
        if isinstance(parent, Topic):
            namespace['parent_summary'] = parent.summary
        if isinstance(parent, ForumBlob):
            namespace['parent_summary'] = parent.summary
        elif isinstance(parent, User):
            namespace['parent_summary'] = parent.username

    output = nodelist.render(context)
    context.pop()
    return output


@block
def pp_blob_child_dimension(context, nodelist, *args, **kwargs):
    '''Takes an object from the context, identifies the submission
    dimension for it's children, and returns the dimension to the context
    as a str that can be used in a pp_url to redirect to submit.html page
    '''

    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object', None)

    try:
        namespace['dimension'] = str(obj.child.get_blob_key())
    except:
        namespace['dimension'] = None

    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_blob_edits(context, nodelist, *args, **kwargs):
    '''Takes an object from the context, identifies the submission
    dimension for it's children, and returns the dimension to the context
    as a str that can be used in a pp_url to redirect to submit.html page
    '''

    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object', None)
    start = kwargs.get('start', 0)
    end = kwargs.get('end', 4)
    edit_num = kwargs.get('edit_num', 1)
    if edit_num == None:
        edit_num = 1
    if obj is not None:
        edits = Edit.objects.filter(object_pk=obj.pk).order_by('time')
        cnt = edits.count()
        if cnt >= 1:
            if cnt-edit_num >= 0:
                namespace['latest_edit'] = edits[cnt-edit_num]
                namespace['latest_edit_pk'] = edits[cnt-edit_num].pk
                #namespace['edits'] = edits[int(start):int(end)]
        namespace['count'] = cnt
        namespace['edit_itr'] = cnt+  1 - edit_num

    output = nodelist.render(context)
    context.pop()

    return output



@block
def pp_blob_getchildren(context, nodelist, *args, **kwargs):
    '''Takes an object from the context, identifies the submission
    dimension for it's children, and returns the dimension to the context
    as a str that can be used in a pp_url to redirect to submit.html page
    '''

    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object', None)

    if obj.child is not None:
        mm = obj.child.model_class()
        c = mm.objects.filter(parent_pk=obj.pk)
        namespace['children'] = c

    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_contenttypes(context, nodelist, *args, **kwargs):
    '''Renders a list of content types, used
    for sorting the main list by content type.
    '''

    context.push()
    namespace = get_namespace(context)

    dimension = kwargs.get('dimension', None)
    obj = kwargs.get('object', None)
    #user = kwargs.get('user', None)

    fds = ForumDimension.objects.filter(is_content=True)
    out = []

    for fd in fds:
        try:
            d = DimensionTracker.objects.get(dimension=fd, object_pk=obj.pk)
            if d.children > 0:
                blob_form, model, verbose_name = get_form(fd.key)

                if not fd.is_admin:
                    out.append((fd.key, verbose_name))
        except:
            pass

    namespace['content_types'] = out
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_show_blobchoices(context, nodelist, *args, **kwargs):
    '''Takes a choice from a list of possible objects that can be created,
        and dynamically loads a form with the required and not required fields.

        Populates the context with a pp_blob.blob_form_type, pp_blob.blob_form,
        and pp_blob.blob_form_html that provide the instance with a form
        and html template for inclusion in the template.
    '''

    context.push()
    namespace = get_namespace(context)

    user = kwargs.get('user', None)

    groups = MyGroup.objects.filter(user=user)

    namespace['choices'] = groups
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_views(context, nodelist, *args, **kwargs):
    """
    Given an object id and model, this returns the object associated.
    """

    context.push()
    namespace = get_namespace(context)
    obj = kwargs.get('object', None)

    views = View.objects.filter(object_pk=obj.pk)
    count = views.count()

    namespace['views'] = views
    namespace['count'] = count
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_object(context, nodelist, *args, **kwargs):
    """
    Given an object id and model, this returns the object associated.
    """

    context.push()
    namespace = get_namespace(context)
    model = kwargs.get('model', None)
    object_pk = kwargs.get('object_pk', None)

    try:
        obj = model.get_object_for_this_type(pk=object_pk)
    except Exception, e:
        obj = str(e)
        #try to see if this is a ctype_pk
        try:
            ctype = ContentType.objects.get(pk=model)
            obj = ctype.get_object_for_this_type(pk=object_pk)
        except:
            pass
    namespace['content_object'] = obj
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_search_items(context, nodelist, *args, **kwargs):

    context.push()
    namespace = get_namespace(context)

    search_key = kwargs.get('search_key', None)

    num = 0
    failed = []
    if search_key is not None:
        results = {}
        registered = {}
        for fd in get_models():
            try:
                mod = fd.get_model()
                if mod not in registered:
                    ctype_pk = ContentType.objects.get_for_model(mod).pk
                    s = search(mod, search_key)
                    results[str(ctype_pk)] = s
                    num += len(s)
                    registered[mod] = True
            except:
                failed.append(mod)

        #search for topics
        s = search(Topic, search_key)
        topics = s
        topic_num = len(s)

        s = search(User, search_key)
        users = s
        user_num = len(s)

        namespace['topics'] = topics
        namespace['results'] = results
        namespace['users'] = users
        namespace['num_results'] = num + topic_num + user_num
        namespace['failed'] = failed

    output = nodelist.render(context)
    context.pop()

    return output


class SearchForm(forms.Form):
    search = forms.CharField(widget=forms.TextInput())