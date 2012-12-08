from django import template
from django import forms
from django.http import HttpResponse, HttpResponseRedirect
from django.utils import simplejson

from django.shortcuts import get_object_or_404
from django.contrib.contenttypes.models import ContentType

from pirate_topics.models import MyGroup

from django.db.models import Q

from pirate_core.views import HttpRedirectException, namespace_get
from pirate_consensus.models import  UpDownVote, Consensus,  ConfirmRankedVote, RankedVote, WeightedVote, RankedDecision, RatingVote, SpectrumHolder
from pirate_core.widgets import HorizRadioRenderer

from customtags.decorators import block_decorator
register = template.Library()
block = block_decorator(register)


RATINGS_CHOICES = (
    (1, "Empty of Value"),
    (2, "Poor"),
    (3, "OK"),
    (4, "Good"),
    (5, "Excellent"),
)

SPECTRUM_CHOICES = {
    1: "Never!",
    2: "Strongly Disagree",
    3: "Disagree",
    4: "Mostly Disagree",
    5: "Pt. of Contention",
    6: "Meh",
    7: "Slightly Agree",
    8: "Mostly Agree",
    9: "Agree",
    10: "Strongly Agree",
    11: "Extremely Agree",
}

SPECTRUM_COLORS = {
    1: "#e11010",
    2: "#e13310",
    3: "#e15610",
    4: "#e17810",
    5: "#e19b10",
    6: "#e1be10",
    7: "#e1e110",
    8: "#bee110",
    9: "#9be110",
    10: "#78e110",
    11: "#56e110",
}

get_namespace = namespace_get('pp_consensus')



class RatingForm(forms.Form):
    form_id = forms.CharField(widget=forms.HiddenInput(), initial="pp_rating_form")
    rating = forms.ChoiceField(choices=RATINGS_CHOICES)
    
class SpectrumForm(forms.Form):
    form_id = forms.CharField(widget=forms.HiddenInput(), initial="pp_spectrum_form")
    spectrum = forms.ChoiceField(choices=SPECTRUM_CHOICES.items())


@block
def pp_get_ranked_decision(context, nodelist, *args, **kwargs):

    context.push()
    namespace = get_namespace(context)

    obj = kwargs.pop('object', None)

    try:
        rv = RankedDecision.objects.get(parent=obj)
    except:
        rv = None

    namespace['ranked_decision'] = rv
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_get_ranked_vote(context, nodelist, *args, **kwargs):

    context.push()
    namespace = get_namespace(context)

    user = kwargs.pop('user', None)
    obj = kwargs.pop('object', None)

    if user.is_authenticated():
        rv = RankedVote.objects.filter(user=user, parent=obj)
        rv = rv.order_by('ranked_vote')
        namespace['objects'] = [(i.nom_cons, i) for i in rv]
        if rv.count() > 0:
            namespace['ranked_vote'] = True
        else:
            namespace['ranked_vote'] = None
        try:
            rnk = ConfirmRankedVote.objects.get(user=user, parent=obj)
            namespace['confirmranked'] = rnk.confirm
            namespace['winner'] = rnk
        except:
            namespace['confirmranked'] = False
    output = nodelist.render(context)
    context.pop()

    return output


#returns teh updownvotes pertaining to an object and a user
@block
def pp_get_votes(context, nodelist, *args, **kwargs):

    context.push()
    namespace = get_namespace(context)

    user = kwargs.pop('user', None)
    obj = kwargs.pop('object', None)

    votes = UpDownVote.objects.filter(object_pk=obj.pk).filter(user=user).order_by('vote')

    namespace['votes'] = votes
    namespace['count'] = votes.count()
    output = nodelist.render(context)
    context.pop()

    return output


#returns the reporting percentage of a consensus object
@block
def pp_get_reporting_percentage(context, nodelist, *args, **kwargs):

    context.push()
    namespace = get_namespace(context)

    obj = kwargs.pop('object', None)
    topic = kwargs.pop('group', None)

    votes = UpDownVote.objects.filter(object_pk=obj.pk)
    groups = MyGroup.objects.filter(topic=topic)

    try:
        namespace['reporting'] = votes.count() / float(groups.count())
    except:
        namespace['reporting'] = 0.0
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_consensus_get(context, nodelist, *args, **kwargs):
    #retrieves a consensus object, places that object into the context.
    #Within this tag block an {include} should populate the html with a
    #consensus_widget that uses the context provided by this tag to create
    #the fields for voting and observing the consensus object.
    """
    Consensus objects tie an object to all of the voting information for that object.
    This tag populates the pp_consensus namespace with a consensus object and related information,
    including the interest, votes, and controversy of the object. If you provide the *user*
    parameter to the template tag, it also populates the context with user specific voting info.

    :param object: id of django.db.models.Model object
    :type object: str 
    :param user: djngo.contrib.auth.models.User object
    :returns:
        * pp_consensus.consensus
            This is the consensus object itself
        * pp_consensus.interest
            Holds the interest integer generated by the ranking algorithm
        * pp_consensus.controversy
            Holds the controversy rating generated by the controversy ranking algorithm
        * pp_consensus.consensus
            This is the consensus object itself
        * pp_consensus.votes
            Number of votes on this object
    :requires user:
        * pp_consensus.user_updown
            Returns user voting information if parameter is present
        * pp_consensus.user_rating
            Returns user voting information if parameter is present

    An example HTML template:

    .. code-block:: html
        :linenos:

        {% pp_consensus_get object=object user=request.user %}
                
                {{pp_consensus.interest}}
                
                {{pp_consensus.consensus}}

                <p> Object has {{pp_consensus.votes}} votes </p>
        {% endpp_consensus_get %}

    """
    context.push()
    namespace = get_namespace(context)

    object_pk = kwargs.pop('object', None)

    if object_pk is None:
        raise ValueError("pp_consensus_get tag requires that a object id be passed "
                             "to it assigned to the 'object=' argument.")
    user = kwargs.pop('user', None)

    try:
        namespace['consensus'] = Consensus.objects.get(object_pk=object_pk)

        namespace['interest'] = namespace['consensus'].interest
        namespace['controversy'] = namespace['consensus'].controversy
        namespace['votes'] = namespace['consensus'].votes

        namespace['content_type'] = namespace['consensus'].content_type
        #user specific rendering of vote info
        #if available include it, else set to None
        try:
            updown = UpDownVote.objects.get(user=user, parent=namespace['consensus']).vote
        except:
            updown = None
        try:
            rate = RatingVote.objects.get(user=user, parent=namespace['consensus']).vote
        except:
            rate = None
        namespace['user_updown'] = updown
        namespace['user_rating'] = rate

    except:
        namespace['consensus'] = None
    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_rating_form(context, nodelist, *args, **kwargs): 
    """
    Populates the context with a RatingForm, allowing users to select what
    voting type is applied to the object or the objects children.
    
    Unless the number of related objects is limited, for example solutions to 
    a problem, plurality voting is required. As the number of objects considered
    for voting increases, it becomes increasingly impossible to rank or apply 
    weighted voting to the entire set.
    """
    context.push()
    namespace = get_namespace(context)

    obj = kwargs.pop('object', None)
    POST = kwargs.pop('POST', None)
    user = kwargs.get('user', None)

    
    if POST is not None and POST.get("form_id") == "pp_rating_form":

        form = RatingForm(POST)
        if form.is_valid():
            rating = form.cleaned_data['rating']
            consensus = Consensus.objects.get(object_pk= obj.pk)
            st = RatingVote(user=user, parent=consensus, vote=rating)
    else:
        try:
            prev_rating = RatingVote.objects.get(user=user, object_pk=obj.pk)
            form = RatingForm(initial={'rating': prev_rating.vote})
        except: form = RatingForm()
        
    namespace['form'] = form

        
    output = nodelist.render(context)
    context.pop()

    return output

@block
def pp_spectrum_form(context, nodelist, *args, **kwargs): 
    """
    Populates the context with a SpectrumForm, allowing users to select what
    voting type is applied to the object or the objects children.
    
    Unless the number of related objects is limited, for example solutions to 
    a problem, plurality voting is required. As the number of objects considered
    for voting increases, it becomes increasingly impossible to rank or apply 
    weighted voting to the entire set.
    """
    context.push()
    namespace = get_namespace(context)

    obj = kwargs.pop('object', None)
    POST = kwargs.pop('POST', None)
    user = kwargs.get('user', None)
    dimenion = kwargs.get('dimension', None)

    
    if POST is not None and POST.get("form_id") == "pp_spectrum_form":

        form = SpectrumForm(POST)
        if form.is_valid():
            rating = form.cleaned_data['spectrum']
            consensus = Consensus.objects.get(object_pk=obj.pk)
            #st = RatingVote(user=user, parent=consensus, vote=rating)
    else:
        try:
            prev_rating = UpDownVote.objects.get(user=user, object_pk=obj.pk)
            form = SpectrumForm(initial={'spectrum': prev_rating.vote})
        except:
            form = SpectrumForm()

    namespace['form'] = form

    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_rating_js(context, nodelist, *args, **kwargs):

    """
    Used to populate the context with 5-star rating javascript. Remember to place this code in the appropriate
    markup. This object requires that the consensus object is in the context. An example
    with a consensus object is shown below.

    :param object: django.db.model.Model object
    :param user: djngo.contrib.auth.models.User object
    :param cons: pirate_consensus.models.Consensus object
    :returns:
        * pp_consensus.rating_js
            block of javascript code

    An example HTML template:

    .. code-block:: html
        :linenos:

            <script type="text/javascript">

                {% pp_consensus_get object=object.id %}   

                    {% if pp_consensus.consensus %}
                          {% pp_rating_js object=object user=user cons=pp_consensus.consensus %}

                           {{pp_consensus.rating_js|safe}} 

                          {% endpp_rating_js %}

                    {% endif %}

                {% endpp_consensus_get %}

            </script>
    """

    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object', None)
    user = kwargs.get('user', None)
    ctype = ContentType.objects.get_for_model(obj)

    if obj:
        if user.is_authenticated():
            RET = """
            $(function(){
                    $("#stars-wrapper-rate""" + str(obj.id) + """").stars({
                       inputType: "select",
                       callback: function(ui, type, value){
                            starvote(""" + "'" + str(obj.id) + "'" + """, value, """ + "'" + str(user.pk) + "', " + "'" + str(obj.pk) + "', " + "'" + str(ctype.pk) + "'" + """);
                       },
                       captionEl: $("#stars-cap-rate"),
                       cancelTitle:'Cancel Rating',
                       cancelValue:-99
                    });
                });
            """
        else:
            RET = """
            $(function(){
                    $("#stars-wrapper-rate""" + str(obj.id) + """").stars({
                       inputType: "select",
                       callback: function(ui, type, value){
                            js_redirect('/p/register');
                       },
                       captionEl: $("#stars-cap-rate"),
                       cancelTitle:'Cancel Rating',
                       cancelValue:-99
                    });
                });
            """
    else:
        RET = ""
    namespace['rating_js'] = RET

    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_spectrum_js(context, nodelist, *args, **kwargs):

    """
    Used to populate the context with 10 point color spectrum voting javascript. Remember to place this code in the appropriate
    markup. This object requires that the consensus object is in the context. An example
    with a consensus object is shown below.

    :param object: django.db.model.Model object
    :param user: djngo.contrib.auth.models.User object
    :param cons: pirate_consensus.models.Consensus object
    :returns:
        * pp_consensus.rating_js
            block of javascript code

    An example HTML template:

    .. code-block:: html
        :linenos:

            <script type="text/javascript">

                {% pp_consensus_get object=object.id %}   

                    {% if pp_consensus.consensus %}
                          {% pp_rating_js object=object user=user cons=pp_consensus.consensus %}

                           {{pp_consensus.rating_js|safe}} 

                          {% endpp_rating_js %}

                          {% pp_spectrum_js object=object user=user cons=pp_consensus.consensus %}

                           {{pp_consensus.spectrum_js|safe}}

                          {% endpp_spectrum_js %}

                    {% endif %}

                {% endpp_consensus_get %}

            </script>
    """

    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object', None)
    user = kwargs.get('user', None)
    ctype = ContentType.objects.get_for_model(obj)

    if obj:
        if user.is_authenticated():
            RET = """
            $(function(){
                    $("#stars-wrapper-spec""" + str(obj.id) + """").stars({
                       inputType: "select",
                       callback: function(ui, type, value){
                            spectrumvote(""" + "'" + str(obj.id) + "'" + """, value, """ + "'" + str(user.pk) + "', " + "'" + str(obj.pk) + "', " + "'" + str(ctype.pk) + "'" + """);
                       },
                       spectrum:true,
                       captionEl: $("#stars-cap-spec"),
                       cancelTitle:'Cancel Vote',
                       cancelValue:-99

                    });
                });
            """
        else:
            RET = """
            $(function(){
                    $("#stars-wrapper-spec""" + str(obj.id) + """").stars({
                       inputType: "select",
                       callback: function(ui, type, value){
                            js_redirect('/p/register');
                       },
                       spectrum:true,
                       captionEl: $("#stars-cap-spec"),
                       cancelTitle:'Cancel Vote',
                       cancelValue:-99

                    });
                });
            """
    else:
        RET = ""
    namespace['spectrum_js'] = RET

    output = nodelist.render(context)
    context.pop()

    return output


@block
def pp_consensus_chart(context, nodelist, *args, **kwargs):

    """
        Does a Temp Check by grabbing the opinion data as well
        as voting aggregates.
    """
    context.push()
    namespace = get_namespace(context)

    obj = kwargs.get('object', None)

    if obj is not None:
        #prepare data for highchart
        dchart = {'type': 'pie', 'name': 'Temperature Check'}
        data = []

        if obj.spectrum is not None:
            for i in SpectrumHolder.objects.filter(spectrum_pk=obj.spectrum.pk):
                if i.value > 0:
                    data.append({'name': SPECTRUM_CHOICES[int(i.vote)], 'y': i.value, 'color': SPECTRUM_COLORS[int(i.vote)]})
            dchart['data'] = data
            namespace['chart_data'] = str([dchart])
            if dchart['data'] != []:
                print dchart['data']
                namespace['chart'] = True
        if obj.rating is not None:
            rating_list = obj.rating.get_list()
            tot = 0.0
            val = 0.0
            for i, weight, num in rating_list:
                val += (i * num)
                tot += num
            if tot > 0:
                namespace['mean_information'] = val / tot
            else:
                namespace['mean_information'] = None
    else:
        namespace['chart'] = False
    output = nodelist.render(context)
    context.pop()

    return output


#: render a <link> tag required to be added to the template at the appropriate locations.
@block
def pp_consensus_css(context, nodelist, *args, **kwargs):
    pass

# pre-fetches all of the user votes that might be referenced by tags on the page, and stores them in the context, as a performance hack, so that the rendering of each widget does not cause a separate query to the data store. This is optional.
@block
def pp_consensus_user_block(context, nodelist, *args, **kwargs):
    pass

@block
def pp_consensus_info(context, nodelist, *args, **kwargs):
    pass 


VOTE_TYPES = (('Ranked Voting', 'Ranked Voting'), ('Weighted Voting','Weighted Voting'), ('Up/Down Voting','Up/Down Voting'))