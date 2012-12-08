from django import template
from django import forms
from django.http import HttpResponseRedirect
import datetime
from django.contrib.contenttypes.models import ContentType
from tagging.models import Tag, TaggedItem
from django.db.models import get_model
from pirate_consensus.models import Consensus
from settings import DOMAIN_NAME, DOMAIN

from pirate_topics.models import add_group_tag
from pirate_forum.templatetags.blobtags import get_form

from pirate_core.helpers import clean_html

from pirate_social.models import RelationshipEvent
from pirate_signals.models import relationship_event
from pirate_social.models import register_relationship_event
from pirate_core import HttpRedirectException, namespace_get, FormMixin

from django.template.defaultfilters import stringfilter
import uuid
from customtags.decorators import block_decorator
register = template.Library()
block = block_decorator(register)

get_namespace = namespace_get('pp_tag')

"""This is more of a group of helper generic templatetags

    TODO: Change the namespace and all hooks to reflect that"""

from django.template.defaultfilters import floatformat


@register.filter
def objectClass(value):
    """
    **Filter**

    Takes a float value and returns it as a percentage. Only makes sense for float values in the range [0,1].

    for example:

.. code-block:: html

        {{object.consensus_percent|percent}}
    """
    if value is None:
        return None
    else:
        return value._meta.verbose_name


@register.filter
def percent(value):
    """
    **Filter**

    Takes a float value and returns it as a percentage. Only makes sense for float values in the range [0,1].

    for example:

.. code-block:: html

        {{object.consensus_percent|percent}}
    """
    if value is None:
        return None
    try:
        return floatformat(value * 100.0, 0) + '%'
    except:
        return '0 %'


@register.filter
def cleansignature(value):
    """
    **Filter**

    Removes ``?`` and everything after from urls.

    for example:

.. code-block:: html

        {{object.file.url|cleansignature}}
    """
    if '?' not in value:
        return value
    t = value.index('?')
    return value[0:t]



##gets an ordered tuple, if we want to user 2 ordered keys as another key, for example 2-way communication between
###users. This way the template can order keys even if received from multiple users
@block
def pp_ordered_tuple(context, nodelist, *args, **kwargs):
    """
    :param key1: Some key or object id
    :type key1: str 
    :param key2: Some key or object id
    :type key2: str 
    :returns:
        * pp_tag.key
            ordered key

    **Usage**

    For instance we might need a unique identifier for 2-users, 2-objects, or something else.
    This template tag is primarily used by the node.js chat as a key in the Redis keystore that represents
    a P2P chat between 2 users.
    """
    context.push()
    namespace = get_namespace(context)

    key1 = kwargs.get('key1', None)
    key2 = kwargs.get('key2', None)

    if key1 is not None and key2 is not None:
        if key1 < key2:
            ret = key1 + key2
        else:
            ret = key2 + key1

    namespace['key'] = ret
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_random_id(context, nodelist, *args, **kwargs):
    """
    Usually used for assigning a random id to guests in chat.

    :param slice: length of random key
    :type slice: int 
    :returns:
        * pp_tag.id
            a randomized id value with length ``slice``

    .. code-block:: html

        {% pp_random_id slice=5 %}

            {{pp_tag.id}}

        {% endrandom_id %}


    """
    context.push()
    namespace = get_namespace(context)

    amt = kwargs.get('slice', None)

    pk = str(uuid.uuid4())

    namespace['id'] = pk[0:int(amt)]
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_slice(context, nodelist, *args, **kwargs):

    """
    :param obj: length of random key
    :type obj: a list of ``QuerySet`` object
    :param amt: length of slice
    :type amt: int
    :returns:
        * pp_tag.sliced
            list sliced similar to the l[0:amt] function in Python

    .. code-block:: html

        {% pp_slice obj=list slice=5 %}

            {{pp_tag.sliced}}

        {% endpp_slice %}


    """
    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('obj', None)
    amt = kwargs.get('amt', None)

    amt = int(amt)
    namespace['sliced'] = str(obj)[0:amt]
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_datetime_less_than(context, nodelist, *args, **kwargs):
    context.push()
    namespace = get_namespace(context)

    time = kwargs.get('time', None)

    if time is not None:
        now = datetime.datetime.now()

        delta = now - time

        diff = 24 * 60 * 60 * delta.days + delta.seconds + delta.microseconds / 1000000.

        if diff < 0:
            namespace['past'] = True
        else:
            namespace['past'] = False

        namespace['now'] = (now - time) > datetime.timedelta(seconds=1)
        namespace['DOMAIN'] = DOMAIN
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_datetime_less_than_2(context, nodelist, *args, **kwargs):
    context.push()
    namespace = get_namespace(context)

    time1 = kwargs.get('time1', None)
    time2 = kwargs.get('time2', None)

    for i, time in (('past1', time1), ('past2', time2)):
        if time is not None:
            now = datetime.datetime.now()

            delta = now - time

            diff = 24 * 60 * 60 * delta.days + delta.seconds + delta.microseconds / 1000000.

            if diff < 0:
                namespace[i] = True
            else:
                namespace[i] = False

    namespace['DOMAIN'] = DOMAIN
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_time_difference_str(context, nodelist, *args, **kwargs): 
    context.push()
    namespace = get_namespace(context)

    then = kwargs.get('then', None)
    short = kwargs.get('short', None)
    now = datetime.datetime.now()

    if then is not None:

        time_to = abs(now - then)
        hours = time_to.seconds / 3600

        if time_to.days != 0:
            ret = str(time_to.days)
            if short is not None:
                ret += " days ago"
            else:
                ret += " days"
        elif hours == 0:
            if time_to.seconds / 60 == 0:
                ret = str(time_to.seconds)
                if short is not None:
                    ret += " seconds ago"
                else:
                    ret += "secs"
            else:
                ret = str(time_to.seconds / 60)
                if short is not None:
                    ret += " minutes ago"
                else:
                    ret += " mins"
        else:
            ret = str(time_to.seconds / 3600)
            if short is not None:
                ret += " hours ago"
            else:
                ret += " hours"

        namespace['dt'] = ret

    output = nodelist.render(context)
    context.pop()

    return output

        
def get_link_tag_list(user,obj,add_tags_in_object=True, get_links=False):
    """Transforms a list of tags into htmls links to add_tag, used in ajax. 
    This link_list is for tag_details, the other list is to add tags Used in combination
    these functions let tag recommendations and insertions occur over ajax/json."""
    opts = obj._meta
        
    al = opts.app_label
    mod = opts.module_name
    
    model = get_model(al, mod)
    filters = {'pk':obj.pk}
    tags = Tag.objects.cloud_for_model(obj,filters=filters)
    
    c_type = ContentType.objects.get_for_model(Tag)
    
    if not get_links: taglist = []
    else: taglist = "<li><b>Tags:</b></li>"
    sortlist = []

###TODO: need to memcache this list
    for t in tags:
            rels = RelationshipEvent.objects.all() #breaking modularity saves some DB space here, RelationShip event stores the info we need
            rels = rels.filter(ini_object_pk=t.pk,tar_object_pk=obj.pk)
            count = rels.count()
            sortlist.append((t,count))
            sortlist = sorted(sortlist, key=lambda x: x[1]) 
            sortlist.reverse()
    for t, count in sortlist:  
            if not get_links: taglist.append((t.name, t.id, c_type.id, count))  
            else:
                taglist += '<li><a href="/index.html#item/_t=' + str(c_type.id) + '/_o=' + str(t.id) + '/_d=hn">' + str(replace_w_space(t.name))  + "(" + str(count) + ")</a>" +"</li>"
            #move to pirate_social and use template tag instead
            #try: 
            #    RelationshipEvent.objects.get(initiator=user,ini_object_pk=t.pk,tar_object_pk=obj.pk)
            #    link += "<a style='color:red;font-size:95%;' href='javascript:;' onClick=" + '"' + "del_tag('" + str(t.name) + "','" + str(obj.id) + "','" + str(mod) + "', '" + str(al) + "');" + '"' + ">x</a></font>" + " "
            #except: link+= " " 
    return taglist


def get_recommended_tag_list(obj, add_tags_in_object=True, get_links=False):
    """Transforms a list of tags into htmls links to add_tag, used in ajax. 
    Grabs tag list or a object's model, ignoring tags from that model to offer
    for recommendation."""
    opts = obj._meta
        
    al = opts.app_label
    mod = opts.module_name
    
    model = get_model(al, mod)

    content_type = ContentType.objects.get_for_model(obj)
    tags = Tag.objects.cloud_for_model(model)
    
    if not add_tags_in_object:
        tags_remove = Tag.objects.get_for_object(obj)
    else:
        tags_remove = []
    if not get_links: taglist = []
    else: taglist = "<div class='inner'><b>Click to Add Recommended Tags:</b></div>"
    itr = 0
    last = False
    max_tags = 50
    if len(tags) > max_tags: tags = tags[0:max_tags]
    for t in tags:
        itr+=1
        if t not in tags_remove:
            try: font_size = t.font_size
            except: font_size = 11
            if not get_links: taglist.append((t.count, t.name, font_size, mod, al))
            else: 
                taglist += "<font size=" + str(font_size) + "><a href='javascript:;'" + ' onClick="' + "add_tag('" + str(t.name) + "','" + str(obj.id) + "','" + str(mod) + "','" + str(al) + "');" + '">' + str(replace_w_space(t.name)) + "</a></font> "
                if itr != len(tags): taglist+=", "
    return taglist
    

@block 
def pp_tag_recommendations(context, nodelist, *args, **kwargs):
    '''
    This block tag can create or process forms to get tags.
    Usage is as follows:

    '''
    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object',None)
    
    if obj != None: taglist = get_recommended_tag_list(obj)
    else: taglist = ''
    
    namespace['taglist'] = taglist

    output = nodelist.render(context)
    context.pop()
    return output  

@block
def pp_get_tags_for_model(context, nodelist, *args, **kwargs):
    '''
    This block tag can create or process forms to get tags.
    Usage is as follows:
    '''
    
    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object',None)
    
    filters = {'pk':obj.pk}
    try: tags = Tag.objects.cloud_for_model(obj,filters=filters)
    except: tags = []

    namespace['tags'] = tags

    output = nodelist.render(context)
    context.pop()
    return output  

@block
def pp_has_tags(context, nodelist, *args, **kwargs):
    '''
    Returns True if "object" has a Tag model associated with it.   
    '''
    
    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object',None)
    
    l = Tag.objects.get_for_object(obj)
    count = l.count()
    if count > 0: ret = True
    else: ret = False
    
    namespace['has_tags'] = ret

    output = nodelist.render(context)
    context.pop()
    return output


@block
def pp_get_tags_for_object(context, nodelist, *args, **kwargs):
    '''
    This block tag can create or process forms to get tags.
    Usage is as follows:
    '''

    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object', None)

    filters = {'pk': obj.pk}
    try:
        tags = Tag.objects.cloud_for_model(obj, filters=filters)
    except:
        tags = []

    namespace['tags'] = tags

    output = nodelist.render(context)
    context.pop()
    return output


@block
def pp_get_tags(context, nodelist, *args, **kwargs):
    '''
    This block tag can create or process forms to get tags.
    Usage is as follows:
    '''

    context.push()
    namespace = get_namespace(context)
    obj = kwargs.get('object', None)
    user = kwargs.get('user', None)

    if obj is not None:
        tags = get_link_tag_list(user, obj)
    else:
        tags = None

    namespace['tags'] = tags
    #namespace['tags'].extend(tags1)
    #namespace['tags'].extend(tags2)
    output = nodelist.render(context)
    context.pop()
    return output


@block
def pp_get_objects_for_tag(context, nodelist, *args, **kwargs):
    '''
    This block tag can create or process forms to get tags.
    Usage is as follows:

    '''

    context.push()
    namespace = get_namespace(context)

    tag = kwargs.get('object',None)
    
    objs = TaggedItem.objects.get_union_by_model(Consensus,tag)
    
    namespace['tagged_objects'] = obj
    
    output = nodelist.render(context)
    context.pop()
    return output    



@block
def pp_tag_form(context, nodelist, *args, **kwargs):
    '''
    This block tag can create or process forms either to create or to modify arguments.
    Usage is as follows:

    {% pp_tag_form POST=request.POST path=request.path object=pp-issue.issue %}
       Do stuff with {{ pp_tag.form }}.
    {% endpp_tag_form %}
    '''

    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object', None)
    POST = kwargs.get('POST', None)
    tag = kwargs.get('tag', None)
    user = kwargs.get('user', None)

    obj_pk = obj.content_object.pk
    ctype_pk = ContentType.objects.get_for_model(obj.content_object).pk

    #obj = Consensus.objects.get(object_pk=content_obj.pk)
    if POST and POST.get("form_id") == "pp_tag_form":

        if tag != None:
            Tag.objects.add_tag(obj, tag.name)
        else:
            form = TagForm(POST)
            #new_arg = form.save(commit=False)
            if form.is_valid():
                tag_list = form.cleaned_data['tag'].split(',')
                for t in tag_list:
                    if len(t) > 0:
                        clean_tag = clean_html(t.replace(' ', '-'))
                        if len(str(clean_tag)) < 32:
                            Tag.objects.add_tag(obj, clean_tag)
                            tag = TaggedItem._default_manager.get(tag_name=clean_tag, object_id=obj.pk)
                            new_tag = tag.tag
                            try:
                                add_group_tag.apply_async(args=[obj_pk, ctype_pk, clean_tag])
                                relationship_event.send(sender=new_tag, obj=new_tag, parent=obj, initiator=user)
                                form = TagForm()
                            except:
                                namespace['errors'] = "You've already used that tag for this object"
                        else:
                            namespace['errors'] = clean_tag + " invalid.<br>Tags cannot be longer than 32 characters."
        #raise HttpRedirectException(HttpResponseRedirect(obj.content_object.get_absolute_url()))
    else:
        form = TagForm()
    namespace['form'] = form
    output = nodelist.render(context)
    context.pop()
    return output


@register.filter
@stringfilter
def replace_w_space(value):
    return value.replace('-', ' ').replace('_', ' ')


class TagForm(forms.Form):

    form_id = forms.CharField(widget=forms.HiddenInput(), initial="pp_tag_form")
    #tag = AutoCompleteSelectField('tag')
    tag = forms.CharField(widget=forms.TextInput(
               attrs={'size': '20', 'class': 'inputText'}), initial="")


class DeleteForm(forms.Form):
    form_id = forms.CharField(widget=forms.HiddenInput(), initial="pp_delete_tag_form")

