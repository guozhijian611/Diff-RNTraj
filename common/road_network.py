import networkx as nx
from rtree import Rtree
from osgeo import ogr
from .spatial_func import SPoint, distance
from .mbr import MBR
import copy
import os


class UndirRoadNetwork(nx.Graph):
    def __init__(self, g, edge_spatial_idx, edge_idx):
        super(UndirRoadNetwork, self).__init__(g)
        # entry: eid
        self.edge_spatial_idx = edge_spatial_idx
        # eid -> edge key (start_coord, end_coord)
        self.edge_idx = edge_idx

    def to_directed(self, as_view=False):
        """
        Convert undirected road network to directed road network
        new edge will have new eid, and each original edge will have two edge with reversed coords
        :return:
        """
        assert as_view is False, "as_view is not supported"
        avail_eid = max([eid for u, v, eid in self.edges.data(data='eid')]) + 1
        g = nx.DiGraph()
        edge_spatial_idx = Rtree()
        edge_idx = {}
        # add nodes
        for n, data in self.nodes(data=True):
            # when data=True, it means will data=node's attributes
            new_data = copy.deepcopy(data)
            g.add_node(n, **new_data)
        # add edges
        for u, v, data in self.edges(data=True):
            mbr = MBR.cal_mbr(data['coords'])
            # add forward edge
            forward_data = copy.deepcopy(data)
            g.add_edge(u, v, **forward_data)
            edge_spatial_idx.insert(forward_data['eid'], (mbr.min_lng, mbr.min_lat, mbr.max_lng, mbr.max_lat))
            edge_idx[forward_data['eid']] = (u, v)
            # add backward edge
            backward_data = copy.deepcopy(data)
            backward_data['eid'] = avail_eid
            avail_eid += 1
            backward_data['coords'].reverse()
            g.add_edge(v, u, **backward_data)
            edge_spatial_idx.insert(backward_data['eid'], (mbr.min_lng, mbr.min_lat, mbr.max_lng, mbr.max_lat))
            edge_idx[backward_data['eid']] = (v, u)
        print('# of nodes:{}'.format(g.number_of_nodes()))
        print('# of edges:{}'.format(g.number_of_edges()))
        return RoadNetwork(g, edge_spatial_idx, edge_idx)

    def range_query(self, mbr):
        """
        spatial range query. Given a mbr, return a range of edges.
        :param mbr: query mbr
        :return: qualified edge keys
        """
        eids = self.edge_spatial_idx.intersection((mbr.min_lng, mbr.min_lat, mbr.max_lng, mbr.max_lat))
        return [self.edge_idx[eid] for eid in eids]

    def remove_edge(self, u, v):
        edge_data = self[u][v]
        coords = edge_data['coords']
        mbr = MBR.cal_mbr(coords)
        # delete self.edge_idx[eid] from edge index
        del self.edge_idx[edge_data['eid']]
        # delete from spatial index
        self.edge_spatial_idx.delete(edge_data['eid'], (mbr.min_lng, mbr.min_lat, mbr.max_lng, mbr.max_lat))
        # delete from graph
        super(UndirRoadNetwork, self).remove_edge(u, v)

    def add_edge(self, u_of_edge, v_of_edge, **attr):
        coords = attr['coords']
        mbr = MBR.cal_mbr(coords)
        attr['length'] = sum([distance(coords[i], coords[i + 1]) for i in range(len(coords) - 1)])
        # add edge to edge index
        self.edge_idx[attr['eid']] = (u_of_edge, v_of_edge)
        # add edge to spatial index
        self.edge_spatial_idx.insert(attr['eid'], (mbr.min_lng, mbr.min_lat, mbr.max_lng, mbr.max_lat))
        # add edge to graph
        super(UndirRoadNetwork, self).add_edge(u_of_edge, v_of_edge, **attr)


class RoadNetwork(nx.DiGraph):
    def __init__(self, g, edge_spatial_idx, edge_idx):
        super(RoadNetwork, self).__init__(g)
        # entry: eid
        self.edge_spatial_idx = edge_spatial_idx
        # eid -> edge key (start_coord, end_coord)
        self.edge_idx = edge_idx

    def range_query(self, mbr):
        """
        spatial range query
        :param mbr: query mbr
        :return: qualified edge keys
        """
        eids = self.edge_spatial_idx.intersection((mbr.min_lng, mbr.min_lat, mbr.max_lng, mbr.max_lat))
        return [self.edge_idx[eid] for eid in eids]

    def remove_edge(self, u, v):
        edge_data = self[u][v]
        coords = edge_data['coords']
        mbr = MBR.cal_mbr(coords)
        # delete self.edge_idx[eifrom edge index
        del self.edge_idx[edge_data['eid']]
        # delete from spatial index
        self.edge_spatial_idx.delete(edge_data['eid'], (mbr.min_lng, mbr.min_lat, mbr.max_lng, mbr.max_lat))
        # delete from graph
        super(RoadNetwork, self).remove_edge(u, v)

    def add_edge(self, u_of_edge, v_of_edge, **attr):
        coords = attr['coords']
        mbr = MBR.cal_mbr(coords)
        attr['length'] = sum([distance(coords[i], coords[i + 1]) for i in range(len(coords) - 1)])
        # add edge to edge index
        self.edge_idx[attr['eid']] = (u_of_edge, v_of_edge)
        # add edge to spatial index
        self.edge_spatial_idx.insert(attr['eid'], (mbr.min_lng, mbr.min_lat, mbr.max_lng, mbr.max_lat))
        # add edge to graph
        super(RoadNetwork, self).add_edge(u_of_edge, v_of_edge, **attr)


def load_rn_shp(path, is_directed=True):
    edge_spatial_idx = Rtree()
    edge_idx = {}
    # NetworkX 3.x removed read_shp; parse edges directly with OGR.
    if os.path.isdir(path):
        edges_shp = os.path.join(path, 'edges.shp')
        if not os.path.exists(edges_shp):
            raise FileNotFoundError(f"Cannot find edges shapefile: {edges_shp}")
    else:
        edges_shp = path

    ds = ogr.Open(edges_shp)
    if ds is None:
        raise FileNotFoundError(f"Failed to open shapefile: {edges_shp}")
    layer = ds.GetLayer(0)

    g = nx.DiGraph()
    layer_defn = layer.GetLayerDefn()
    field_names = [layer_defn.GetFieldDefn(i).GetName() for i in range(layer_defn.GetFieldCount())]

    for feature in layer:
        geom_line = feature.GetGeometryRef()
        if geom_line is None or geom_line.GetPointCount() < 2:
            continue

        coords = []
        for i in range(geom_line.GetPointCount()):
            lng, lat, *_ = geom_line.GetPoint(i)
            coords.append(SPoint(lat, lng))

        u = (coords[0].lng, coords[0].lat)
        v = (coords[-1].lng, coords[-1].lat)
        g.add_node(u, pt=SPoint(u[1], u[0]))
        g.add_node(v, pt=SPoint(v[1], v[0]))

        data = {name: feature.GetField(name) for name in field_names}
        eid = data.get('fid', feature.GetFID())
        if eid is None:
            eid = feature.GetFID()
        eid = int(eid)
        while eid in edge_idx:
            eid += 1

        data['eid'] = eid
        data['coords'] = coords
        data['length'] = sum([distance(coords[i], coords[i + 1]) for i in range(len(coords) - 1)])
        g.add_edge(u, v, **data)

        env = geom_line.GetEnvelope()
        edge_spatial_idx.insert(eid, (env[0], env[2], env[1], env[3]))
        edge_idx[eid] = (u, v)

    if not is_directed:
        g = g.to_undirected()
    print('# of nodes:{}'.format(g.number_of_nodes()))
    print('# of edges:{}'.format(g.number_of_edges()))
    if not is_directed:
        return UndirRoadNetwork(g, edge_spatial_idx, edge_idx)
    else:
        return RoadNetwork(g, edge_spatial_idx, edge_idx)


def store_rn_shp(rn, target_path):
    print('# of nodes:{}'.format(rn.number_of_nodes()))
    print('# of edges:{}'.format(rn.number_of_edges()))
    for _, data in rn.nodes(data=True):
        if 'pt' in data:
            del data['pt']
    for _, _, data in rn.edges(data=True):
        geo_line = ogr.Geometry(ogr.wkbLineString)
        for coord in data['coords']:
            geo_line.AddPoint(coord.lng, coord.lat)
        data['Wkb'] = geo_line.ExportToWkb()
        del data['coords']
        if 'length' in data:
            del data['length']
    if not rn.is_directed():
        rn = rn.to_directed()
    nx.write_shp(rn, target_path)
