'use strict';

angular.module('deepsense.graph-model').
  factory('Workflow', /*@ngInject*/function(GraphNode, Edge) {
    function Workflow() {
      var that = this;
      var internal = {};
      internal.nodes = {};
      internal.edges = {};

      that.STATUS = {
        'DRAFT':     'status_draft',
        'RUNNING':   'status_running',
        'COMPLETED': 'status_completed',
        'FAILED':    'status_failed',
        'ABORTED':   'status_aborted'
      };
      that.STATUS_DEFAULT = that.STATUS.DRAFT;

      that.getId = function getId() {
        return internal.id;
      };

      that.clearGraph = function clearGraph() {
        internal.nodes = {};
        internal.edges = {};
      };

      that.getNodes = function getNodes() {
        return internal.nodes;
      };

      that.getNodesIds = function getNodesIds() {
        return _.map(internal.nodes, (node) => node.id);
      };

      that.getNodeById = function getNodeById(nodeId) {
        return internal.nodes[nodeId];
      };

      that.getEdges = function getEdges() {
        return internal.edges;
      };

      that.getEdgeById = function getEdgeById(edgeId) {
        return internal.edges[edgeId];
      };

      that.getNeightbours = function getNeightbours(nodeId) {
        return _.map(
          _.filter(that.getEdgesByNodeId(nodeId), (neibourEdge) => neibourEdge.startNodeId === nodeId),
          (neibourEdge) => neibourEdge.endNodeId
        );
      };

      that.createNode = function createNode(options) {
        let operation = options.operation;

        return new GraphNode({
          'id': options.id,
          'name': operation.name,
          'operationId': operation.id,
          'version': operation.version,
          'icon': operation.icon,
          'parametersValues': options.parameters || {},
          'description': operation.description,
          'input': operation.ports.input,
          'output': operation.ports.output,
          'x': options.x,
          'y': options.y,
          'state': options.state
        });
      };

      that.createNodes = function createNodes(nodes, operations, thirdPartyData) {
        let getCoordinate = (id, cord) => {
          try {
            return thirdPartyData.gui.nodes[id].coordinates[cord];
          } catch(e) {
            return 0;
          }
        };

        for (let i = 0; i < nodes.length; i++) {
          let data = nodes[i];
          let id = data.id;
          let operation = operations[data.operation.id];
          let node = that.createNode({
              'id': id,
              'operation': operation,
              'parameters': data.parameters,
              'x': getCoordinate(id, 'x'),
              'y': getCoordinate(id, 'y')
              //'state': state.nodes[id]
            });
          that.addNode(node);
        }
      };

      that.removeEdges = function removeEdges(nodeId) {
        for (var edge in internal.nodes[nodeId].edges) {
          that.removeEdge(internal.nodes[nodeId].edges[edge]);
        }
      };

      that.getEdgesByNodeId = function getEdgesByNodeId(nodeId) {
        return internal.nodes[nodeId].edges;
      };

      that.setData = function setData(data) {
        internal.id = data.id;
        internal.name = data.name;
        internal.description = data.description;
      };

      that.setStatus = function setStatus(state) {
        if (state && state.status && Object.keys(that.STATUS).indexOf(state.status) > -1) {
          that.status = that.STATUS[state.status];
        }
      };

      that.getStatus = function getStatus() {
        return that.status || that.STATUS_DEFAULT;
      };

      that.updateState = function updateState(state) {
        for (let id in state.nodes) {
          let node = internal.nodes[id];
          if (node) {
            node.updateState(state.nodes[id]);
          }
        }
        that.setStatus(state);
      };

      that.isRunning = function isRunning() {
        return that.getStatus() === that.STATUS.RUNNING;
      };

      that.addNode = function addNode(node) {
        if (that.getNodeById(node.id)) {
          throw new Error('Node ' + node.id + ' already exists');
        }
        internal.nodes[node.id] = node;
      };

      that.addEdge = function addEdge(edge) {

        if (!edge.id) {
          throw new Error('Cannot add edge without id set.');
        }
        else if (!that.getNodeById(edge.startNodeId)) {
          throw new Error('Cannot create edge between nodes. Start node id: ' + edge.startNodeId + ' doesn\'t exist.');
        }
        else if (!that.getNodeById(edge.endNodeId)) {
          throw new Error('Cannot create edge between nodes. End node id: ' + edge.endNodeId + ' doesn\'t exist.');
        }

        internal.edges[edge.id] = edge;
        that.getNodeById(edge.startNodeId).edges[edge.id] = edge;
        that.getNodeById(edge.endNodeId).edges[edge.id] = edge;
      };

      that.removeEdge = function removeEdge(edge) {
        if (!edge.id) {
          throw new Error('Cannot remove edge. Edge id: ' + edge.id + ' doesn\'t exist.');
        }
        else if (!that.getNodeById(edge.startNodeId)) {
          throw new Error('Cannot remove edge between nodes. Start node id: ' + edge.startNodeId + ' doesn\'t exist.');
        }
        else if (!that.getNodeById(edge.startNodeId)) {
          throw new Error('Cannot remove edge between nodes. End node id: ' + edge.endNodeId + ' doesn\'t exist.');
        }

        delete internal.edges[edge.id];
        delete internal.nodes[edge.startNodeId].edges[edge.id];
        delete internal.nodes[edge.endNodeId].edges[edge.id];
      };

      that.removeNode = function removeNode(nodeId) {
        try {
          that.removeEdges(nodeId);
          delete internal.nodes[nodeId];
        }
        catch (error) {
          throw new Error('Cannot remove node. Node id: ' + nodeId + ' doesn\'t exist.');
        }
      };

      that.createEdge = function createEdge(data) {
        var edge = new Edge({
          startNodeId: data.from.nodeId,
          startPortId: data.from.portIndex,
          endNodeId: data.to.nodeId,
          endPortId: data.to.portIndex
        });
        return edge;
      };

      that.createEdges = function createEdges(edges) {
        for (var i = 0; i < edges.length; i++) {
          var edge = that.createEdge(edges[i]);
          that.addEdge(edge);
        }
      };

      that.serialize = function serialize() {
        let data = {
          'id': internal.id,
          'workflow': {
            'nodes': [],
            'connections': []
          },
          'thirdPartyData': {
            'gui': {
              'name': internal.name,
              'description': internal.description,
              'nodes': {

              }
            }
          }
        };

        for (let id in internal.nodes) {
          data.workflow.nodes.push(internal.nodes[id].serialize());
          data.thirdPartyData.gui.nodes[id] = {
            coordinates: {
              x: internal.nodes[id].x,
              y: internal.nodes[id].y
            }
          };
        }

        for (let id in internal.edges) {
          data.workflow.connections.push(internal.edges[id].serialize());
        }

        return data;
      };

      that.updateTypeKnowledge = function (knowledge) {
        _.forEach(this.getNodes(), (node) => {
          if (knowledge[node.id] && knowledge[node.id].typeKnowledge) {
            let newOutputPorts = knowledge[node.id].typeKnowledge;
            _.forEach(node.output, (port) => {
              let newTypes = newOutputPorts[port.index];
              if (newTypes) {
                port.typeQualifier = newTypes.slice();
              }
            });
          }
        });
      };

      that.updateEdgesStates = function (OperationsHierarchyService) {
        let nodes = this.getNodes();

        _.forEach(this.getEdges(), (edge) => {
          let startNode = nodes[edge.startNodeId];
          let endNode = nodes[edge.endNodeId];
          let outputTypes = _.find(startNode.output, (port) => port.index === edge.startPortId).typeQualifier;
          let inputTypes = _.find(endNode.input, (port) => port.index === edge.endPortId).typeQualifier;

          let numberOfValidTypes = 0;
          _.each(outputTypes, (outputType) => {
            numberOfValidTypes += (OperationsHierarchyService.IsDescendantOf(outputType, inputTypes) ? 1 : 0);
          });

          if (numberOfValidTypes === outputTypes.length) {
            edge.state = Edge.STATE_TYPE.ALWAYS;
          } else if (numberOfValidTypes === 0) {
            edge.state = Edge.STATE_TYPE.NEVER;
          } else {
            edge.state = Edge.STATE_TYPE.MAYBE;
          }
        });
      };
    }

    return Workflow;
  });