from django.http import HttpResponse
import simplejson
import BeautifulSoup
from oa_dashboard.tasks import async_sort_board, async_del_board, save_board
from oa_cache.views import render_hashed
from oa_dashboard.models import DashboardPanel
from oa_cache.models import interpret_hash, build_hash
from django.template.loader import render_to_string


def decrease_zoom(request):
    if not request.user.is_authenticated()  or not request.user.is_active:
        #needs to popup registration dialog instead
        return HttpResponse(simplejson.dumps({'FAIL': True}),
                                mimetype='application/json')

    if request.method == 'POST':
        obj_pk = request.POST[u'object_pk']
        dim = request.POST[u'dimension']

        db = DashboardPanel.objects.get(pk=obj_pk)
        if dim == 'X':
            db.zoom_x -= 1
        if dim == 'Y':
            db.zoom_y -= 1
        db.save()

        results = {'FAIL': False}

        return HttpResponse(simplejson.dumps(results),
                    mimetype='application/json')


def increase_zoom(request):
    if not request.user.is_authenticated()  or not request.user.is_active:
        #needs to popup registration dialog instead
        return HttpResponse(simplejson.dumps({'FAIL': True}),
                                mimetype='application/json')

    if request.method == 'POST':
        obj_pk = request.POST[u'object_pk']
        dim = request.POST[u'dimension']

        db = DashboardPanel.objects.get(pk=obj_pk)
        if dim == 'X':
            db.zoom_x += 1
        if dim == 'Y':
            db.zoom_y += 1
        db.save()

        results = {'FAIL': False}

        return HttpResponse(simplejson.dumps(results),
                    mimetype='application/json')


def add_board(request):
    if not request.user.is_authenticated()  or not request.user.is_active:
        #needs to popup registration dialog instead
        return HttpResponse(simplejson.dumps({'FAIL': True}),
                                mimetype='application/json')
    results = {}
    if request.method == 'POST':
        path = request.POST[u'path']
        dashboard_id = request.POST[u'dashboard_id']
        functype = request.POST[u'type']
        boardname = request.POST[u'boardname']
        start = request.POST.get('start', 0)
        end = request.POST.get('end', 20)
        #for pagination

        if functype != 'refresh':
            dashobj = save_board(path, dashboard_id, request.user, boardname)
        else:
            dashobj = DashboardPanel.objects.get(plank=path, dashboard_id=dashboard_id, user=request.user)
        path += '/s-' + str(start) + '/e-' + str(end)

        ret, obj, rtype = render_hashed(request, path, request.user, extracontext={'dashobj': dashobj, 'start': int(start), 'end': int(end)})

        if rtype == 'chat':
            width = render_to_string('stream/stream_width.html', {'dashobj': dashobj})
            height = render_to_string('stream/stream_height.html', {'dashobj': dashobj})
            results = {'width': width, 'height': height}
        html = render_to_string('nav/board_template.html', {'board': ret, 'obj': obj, 'dashobj': dashobj, 'start': int(start), 'end': int(end)})
        if functype == 'refresh':
            soup = BeautifulSoup.BeautifulSoup(html)
            v = soup.find("div", id='content' + str(dashobj.pk))
            html = unicode(v.prettify())
        results.update({'FAIL': False, 'html': html, 'dashpk': dashobj.pk, 'dashzoom_y': dashobj.zoom_y, 'dashzoom_x': dashobj.zoom_x, 'rendertype': rtype})

        return HttpResponse(simplejson.dumps(results),
                    mimetype='application/json')


def sort_board(request):
    if not request.user.is_authenticated()  or not request.user.is_active:
        #needs to popup registration dialog instead
        return HttpResponse(simplejson.dumps({'FAIL': True}),
                                mimetype='application/json')

    if request.method == 'POST':
        sorted_str = request.POST[u'sorted']

        sorted_list = sorted_str.split(',')
        async_sort_board.apply_async(args=[sorted_list])
        results = {'FAIL': False}

        return HttpResponse(simplejson.dumps(results),
                    mimetype='application/json')


def resort_board(request):
    if not request.user.is_authenticated()  or not request.user.is_active:
        #needs to popup registration dialog instead
        return HttpResponse(simplejson.dumps({'FAIL': True}),
                                mimetype='application/json')

    if request.method == 'POST':
        d_id = request.POST[u'dashboard_id']
        dim = request.POST[u'sort_key']

        dash = DashboardPanel.objects.get(pk=d_id)
        key, rendertype, paramdict = interpret_hash(dash.plank)
        paramdict['DIM_KEY'] = dim
        key = build_hash(rendertype, paramdict, add_domain=False)
        dash.plank = key
        dash.save()

        results = {'FAIL': False, 'dash_id': dash.dashboard_id, 'plank': dash.plank}

        return HttpResponse(simplejson.dumps(results),
                    mimetype='application/json')


def del_board(request):
    if not request.user.is_authenticated()  or not request.user.is_active:
        #needs to popup registration dialog instead
        return HttpResponse(simplejson.dumps({'FAIL': True}),
                                mimetype='application/json')

    if request.method == 'POST':
        obj_pk = request.POST[u'object_pk']
        async_del_board.apply_async(args=[obj_pk])

        results = {'FAIL': False}

        return HttpResponse(simplejson.dumps(results),
                    mimetype='application/json')
