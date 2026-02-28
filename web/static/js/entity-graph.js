/**
 * entity-graph.js — D3 force-directed network graph for Entity Network tool.
 *
 * Usage:
 *   EntityGraph.init('#graph-container', data, onNodeClick)
 *   EntityGraph.destroy()
 *
 * data shape:
 *   {
 *     central: { id, label, permit_count },
 *     nodes: [{ id, label, type, permit_count, license, avg_days }],
 *     edges: [{ source, target, rel_type }]
 *   }
 *
 * Dependencies: d3 v7 (loaded from CDN in template)
 */

var EntityGraph = (function () {
    'use strict';

    var _svg = null;
    var _sim = null;

    // Design token colours (match CSS custom properties)
    var COLORS = {
        obsidian:       '#0a0a0f',
        obsidianMid:    '#12121a',
        obsidianLight:  '#1a1a26',
        glassBorder:    'rgba(255,255,255,0.06)',
        glassHover:     'rgba(255,255,255,0.10)',
        accent:         '#5eead4',
        textPrimary:    'rgba(255,255,255,0.92)',
        textSecondary:  'rgba(255,255,255,0.55)',
        textTertiary:   'rgba(255,255,255,0.30)',
        signalGreen:    '#34d399',
        signalAmber:    '#fbbf24',
        signalBlue:     '#60a5fa',
    };

    // Node color by professional role
    var REL_COLORS = {
        contractor:  COLORS.signalAmber,
        architect:   COLORS.accent,
        engineer:    COLORS.signalBlue,
        owner:       COLORS.signalGreen,
        central:     COLORS.accent,
        default:     COLORS.textSecondary,
    };

    function _relColor(type) {
        return REL_COLORS[type] || REL_COLORS.default;
    }

    /**
     * init — render the graph into the given container selector.
     *
     * @param {string}   containerSelector  CSS selector for the wrapping element
     * @param {object}   data               Graph data (see module header)
     * @param {function} onNodeClick        Called with node object when a node is clicked
     */
    function init(containerSelector, data, onNodeClick) {
        destroy(); // clean any previous instance

        var container = document.querySelector(containerSelector);
        if (!container) return;

        var W = container.clientWidth  || 600;
        var H = container.clientHeight || 400;

        // Build node/link arrays
        var centralNode = {
            id:           data.central.id,
            label:        data.central.label,
            type:         'central',
            permit_count: data.central.permit_count || 0,
            license:      null,
            avg_days:     null,
            _central:     true,
        };

        var nodesById = {};
        nodesById[centralNode.id] = centralNode;

        var nodes = [centralNode];
        (data.nodes || []).forEach(function (n) {
            var node = {
                id:           n.id,
                label:        n.label || n.id,
                type:         n.type || 'default',
                permit_count: n.permit_count || 0,
                license:      n.license || null,
                avg_days:     n.avg_days || null,
                _central:     false,
            };
            nodesById[node.id] = node;
            nodes.push(node);
        });

        var links = (data.edges || []).map(function (e) {
            return {
                source:   e.source,
                target:   e.target,
                rel_type: e.rel_type || 'default',
            };
        });

        // Node radius: proportional to permit count, clamped
        function nodeRadius(n) {
            if (n._central) return 18;
            var base = 6;
            var extra = Math.min(n.permit_count / 5, 12);
            return base + extra;
        }

        // SVG
        _svg = d3.select(container)
            .append('svg')
            .attr('width', W)
            .attr('height', H)
            .attr('aria-label', 'Entity network graph')
            .style('display', 'block');

        // Background
        _svg.append('rect')
            .attr('width', W)
            .attr('height', H)
            .attr('fill', COLORS.obsidianMid);

        var g = _svg.append('g');

        // Zoom
        var zoom = d3.zoom()
            .scaleExtent([0.3, 4])
            .on('zoom', function (event) {
                g.attr('transform', event.transform);
            });
        _svg.call(zoom);

        // Simulation
        _sim = d3.forceSimulation(nodes)
            .force('link', d3.forceLink(links)
                .id(function (d) { return d.id; })
                .distance(90)
            )
            .force('charge', d3.forceManyBody().strength(-180))
            .force('center', d3.forceCenter(W / 2, H / 2))
            .force('collision', d3.forceCollide().radius(function (d) {
                return nodeRadius(d) + 8;
            }));

        // Links
        var link = g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(links)
            .join('line')
            .attr('stroke', function (d) { return _relColor(d.rel_type); })
            .attr('stroke-opacity', 0.35)
            .attr('stroke-width', 1.5);

        // Edge labels
        var edgeLabel = g.append('g')
            .attr('class', 'edge-labels')
            .selectAll('text')
            .data(links)
            .join('text')
            .attr('text-anchor', 'middle')
            .attr('font-family', "'JetBrains Mono', monospace")
            .attr('font-size', '9px')
            .attr('fill', COLORS.textTertiary)
            .attr('pointer-events', 'none')
            .text(function (d) { return d.rel_type; });

        // Node groups
        var node = g.append('g')
            .attr('class', 'nodes')
            .selectAll('g')
            .data(nodes)
            .join('g')
            .attr('cursor', 'pointer')
            .on('click', function (event, d) {
                event.stopPropagation();
                if (typeof onNodeClick === 'function') {
                    onNodeClick(d);
                }
            });

        // Drag behaviour
        node.call(
            d3.drag()
                .on('start', function (event, d) {
                    if (!event.active) _sim.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on('drag', function (event, d) {
                    d.fx = event.x;
                    d.fy = event.y;
                })
                .on('end', function (event, d) {
                    if (!event.active) _sim.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                })
        );

        // Circle
        node.append('circle')
            .attr('r', nodeRadius)
            .attr('fill', function (d) {
                return d._central ? COLORS.accent : COLORS.obsidianLight;
            })
            .attr('stroke', function (d) {
                return d._central ? COLORS.accent : _relColor(d.type);
            })
            .attr('stroke-width', function (d) { return d._central ? 0 : 1.5; })
            .attr('fill-opacity', function (d) { return d._central ? 0.15 : 1; });

        // Hover highlight
        node.on('mouseenter', function (event, d) {
            d3.select(this).select('circle')
                .attr('stroke-width', 2.5)
                .attr('stroke', COLORS.accent);
        }).on('mouseleave', function (event, d) {
            d3.select(this).select('circle')
                .attr('stroke-width', d._central ? 0 : 1.5)
                .attr('stroke', d._central ? COLORS.accent : _relColor(d.type));
        });

        // Label
        node.append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', function (d) { return nodeRadius(d) + 14; })
            .attr('font-family', "'IBM Plex Sans', sans-serif")
            .attr('font-size', '11px')
            .attr('fill', COLORS.textSecondary)
            .attr('pointer-events', 'none')
            .text(function (d) {
                var max = 18;
                return d.label.length > max ? d.label.slice(0, max - 1) + '\u2026' : d.label;
            });

        // Permit count badge (only for non-central nodes with count > 0)
        node.filter(function (d) { return !d._central && d.permit_count > 0; })
            .append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', '0.35em')
            .attr('font-family', "'JetBrains Mono', monospace")
            .attr('font-size', '9px')
            .attr('fill', function (d) { return _relColor(d.type); })
            .attr('pointer-events', 'none')
            .text(function (d) { return d.permit_count; });

        // Tick
        _sim.on('tick', function () {
            link
                .attr('x1', function (d) { return d.source.x; })
                .attr('y1', function (d) { return d.source.y; })
                .attr('x2', function (d) { return d.target.x; })
                .attr('y2', function (d) { return d.target.y; });

            edgeLabel
                .attr('x', function (d) { return (d.source.x + d.target.x) / 2; })
                .attr('y', function (d) { return (d.source.y + d.target.y) / 2; });

            node.attr('transform', function (d) {
                return 'translate(' + d.x + ',' + d.y + ')';
            });
        });
    }

    /**
     * destroy — remove svg and stop simulation.
     */
    function destroy() {
        if (_sim) { _sim.stop(); _sim = null; }
        if (_svg) { _svg.remove(); _svg = null; }
    }

    return { init: init, destroy: destroy };
})();
