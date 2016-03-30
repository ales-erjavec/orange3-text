# coding: utf-8
import re
from collections import defaultdict, Counter
from itertools import chain

import numpy as np

from PyQt4 import QtCore, QtGui
from PyQt4.QtCore import Qt, QObject, QUrl

from Orange.widgets import widget, gui, settings
from Orange.widgets.utils import webview
from Orange.data import Table
from orangecontrib.text.corpus import Corpus
from orangecontrib.text.country_codes import \
    CC_EUROPE, INV_CC_EUROPE, SET_CC_EUROPE, \
    CC_WORLD, INV_CC_WORLD, \
    CC_USA, INV_CC_USA, SET_CC_USA

if webview.HAVE_WEBENGINE:
    WebViewClass = webview.WebEngineView
elif webview.HAVE_WEBKIT:
    WebViewClass = webview.WebKitView
else:
    raise ImportError("No supported web view")

CC_NAMES = re.compile('[\w\s\.\-]+')


class Map:
    WORLD = 'world_mill_en'
    EUROPE = 'europe_mill_en'
    USA = 'us_aea_en'
    all = (('World',  WORLD),
           ('Europe', EUROPE),
           ('USA',    USA))


HTML = '''
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body, #map {{margin:0px;padding:0px;width:100%;height:100%;}}
</style>
<link  href="resources/jquery-jvectormap-2.0.2.css" rel="stylesheet">
<script src="resources/jquery-2.1.4.min.js"></script>
<script src="resources/jquery-jvectormap-2.0.2.min.js"></script>
<script src="resources/jquery-jvectormap-world-mill-en.js"></script>
<script src="resources/jquery-jvectormap-europe-mill-en.js"></script>
<script src="resources/jquery-jvectormap-us-aea-en.js"></script>
<script src="resources/geomap-script.js"></script>
<script>
REGIONS = {};
</script>
</head>
<body>
<div id="map"></div>
</body>
</html>'''.format({Map.WORLD: CC_WORLD,
                   Map.EUROPE: CC_EUROPE,
                   Map.USA: CC_USA})


class OWGeoMap(widget.OWWidget):
    name = "GeoMap"
    priority = 20000
    icon = "icons/GeoMap.svg"
    inputs = [("Data", Table, "on_data")]
    outputs = [('Corpus', Corpus)]

    want_main_area = False

    selected_attr = settings.Setting(0)
    selected_map = settings.Setting(0)
    regions = settings.Setting([])

    class _PyBridge(QObject):
        def __init__(self, parent=None, bridged=None):
            super().__init__(parent)
            self.bridged = bridged

        @QtCore.pyqtSlot("QVariantList")
        def region_selected(self, regions):
            """Called from JavaScript"""
            self.bridged.region_selected(regions)

    def __init__(self):
        super().__init__()
        self.data = None
        self.metas = []
        self.webview = None
        self._create_layout()

    def region_selected(self, regions):
        if not regions:
            self.regions = []
            return self.send('Corpus', None)
        self.regions = [str(r) for r in regions]
        attr = self.metas[self.selected_attr]
        if attr.is_discrete: return  # TODO, FIXME: make this work for discrete attrs also
        from Orange.data.filter import FilterRegex
        filter = FilterRegex(attr, r'\b{}\b'.format(r'\b|\b'.join(self.regions)), re.IGNORECASE)
        self.send('Corpus', self.data._filter_values(filter))

    def _create_layout(self):
        box = gui.widgetBox(self.controlArea,
                            orientation='horizontal')
        self.attr_combo = gui.comboBox(box, self, 'selected_attr',
                                       orientation='horizontal',
                                       label='Region attribute:',
                                       callback=self.on_attr_change)
        self.map_combo = gui.comboBox(box, self, 'selected_map',
                                      orientation='horizontal',
                                      label='Map type:',
                                      callback=self.on_map_change,
                                      items=Map.all)
        hexpand = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                                    QtGui.QSizePolicy.Fixed)
        self.attr_combo.setSizePolicy(hexpand)
        self.map_combo.setSizePolicy(hexpand)

        self.webview = WebViewClass(
            self.controlArea, OWGeoMap._PyBridge(self, self),
            contextMenuPolicy=Qt.NoContextMenu
        )
        self.webview.loadFinished.connect(self.__on_webview_load)
        self.webview.setHtml(HTML, QUrl.fromLocalFile(__file__))
        self.controlArea.layout().addWidget(self.webview)

    def __on_webview_load(self):
        self.redraw_webview_map()

    def _repopulate_attr_combo(self, data):
        self.metas = [a for a in chain(data.domain.metas,
                                       data.domain.attributes,
                                       data.domain.class_vars)
                      # Filter string variables
                      if (a.is_discrete and a.values and isinstance(a.values[0], str) and not a.ordered or
                          a.is_string)] if data else []
        self.attr_combo.clear()
        self.selected_attr = 0
        for i, var in enumerate(self.metas):
            self.attr_combo.addItem(gui.attributeIconDict[var], var.name)
            # Select default attribute
            if var.name.lower() == 'country':
                self.selected_attr = i
        if self.metas:
            self.attr_combo.setCurrentIndex(self.attr_combo.findText(self.metas[self.selected_attr].name))

    def on_data(self, data):
        if data is not None and not isinstance(data, Corpus):
            data = Corpus.from_table(data.domain, data)
        self.data = data
        self._repopulate_attr_combo(data)
        if data is None:
            self.region_selected([])
            self.redraw_webview_map()
        else:
            self.on_attr_change()

    def on_map_change(self, map_code=''):
        if map_code:
            self.map_combo.setCurrentIndex(self.map_combo.findData(map_code))
        else:
            map_code = self.map_combo.itemData(self.selected_map)
        self.redraw_webview_map()

    def redraw_webview_map(self):
        map_code = self.map_combo.itemData(self.selected_map)
        if self.data is not None:
            map_code = self.map_combo.itemData(self.selected_map)
            inv_cc_map, cc_map = {
                Map.USA: (INV_CC_USA, CC_USA),
                Map.WORLD: (INV_CC_WORLD, CC_WORLD),
                Map.EUROPE: (INV_CC_EUROPE, CC_EUROPE)}[map_code]

            data = defaultdict(int)
            for cc in getattr(self, 'cc_counts', ()):
                key = inv_cc_map.get(cc, cc)
                if key in cc_map:
                    data[key] += self.cc_counts[cc]
        else:
            data = {}

        script_template = """
        if (typeof renderMap !== "undefined") {{
            DATA = {};
            MAP_CODE = "{}";
            SELECTED_REGIONS = {};
            renderMap();
            "Success";
        }} else {{
            "Try again";
        }}
        """
        script = script_template.format(dict(data), map_code, self.regions)
        self.webview.runJavaScript(script, print)

    def on_attr_change(self):
        attr = self.metas[self.selected_attr]
        if attr.is_discrete:
            self.warning(0, 'Discrete region attributes not yet supported. Patches welcome!')
            return
        countries = (set(map(str.strip, CC_NAMES.findall(i.lower()))) if len(i) > 3 else (i,)
                     for i in self.data.get_column_view(self.data.domain.index(attr))[0])
        def flatten(seq):
            return (i for sub in seq for i in sub)
        self.cc_counts = Counter(flatten(countries))
        # Auto-select region map
        values = set(self.cc_counts)
        if 0 == len(values - SET_CC_USA):
            map_code = Map.USA
        elif 0 == len(values - SET_CC_EUROPE):
            map_code = Map.EUROPE
        else:
            map_code = Map.WORLD
        self.on_map_change(map_code)


def main():
    from Orange.data import Table, Domain, ContinuousVariable, StringVariable

    words = np.column_stack([
        'Slovenia Slovenia SVN USA Iraq Iraq Iraq Iraq France FR'.split(),
        'Slovenia Slovenia SVN France FR Austria NL GB GB GB'.split(),
        'Alabama AL Texas TX TX TX MS Montana US-MT MT'.split(),
    ])
    metas = [
        StringVariable('World'),
        StringVariable('Europe'),
        StringVariable('USA'),
    ]
    domain = Domain([], metas=metas)
    table = Table.from_numpy(domain,
                             X=np.zeros((len(words), 0)),
                             metas=words)
    app = QtGui.QApplication([''])
    w = OWGeoMap()
    w.on_data(table)
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
