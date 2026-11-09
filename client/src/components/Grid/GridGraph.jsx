import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { getGridTopology } from '../../services/api';
import { getVoltageColor, getLoadingColor } from '../../utils/formatters';

export default function GridGraph({ gridState, highlightBus, listings = [], role, onBusClick }) {
  const svgRef = useRef(null);
  const [topology, setTopology] = useState(null);

  // Fetch topology once (it's static)
  useEffect(() => {
    getGridTopology()
      .then(setTopology)
      .catch(err => console.error('Failed to load topology:', err));
  }, []);

  // Render D3 visualization
  useEffect(() => {
    if (!topology || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth || 600;
    const height = 400;

    svg.attr('viewBox', `0 0 ${width} ${height}`);

    // Build bus voltage/violation map from grid state
    const busVoltages = {};
    const busViolations = new Set();
    const lineLoadings = {};
    const lineViolations = new Set();

    if (gridState?.buses) {
      gridState.buses.forEach(b => {
        busVoltages[b.bus_id] = b.voltage_pu;
        if (b.is_violation) busViolations.add(b.bus_id);
      });
    }
    if (gridState?.lines) {
      gridState.lines.forEach(l => {
        lineLoadings[l.line_id] = l.loading_percent;
        if (l.is_violation) lineViolations.add(l.line_id);
      });
    }

    // Build listings lookup by bus_id
    const listingByBus = {};
    listings.forEach(l => { listingByBus[l.bus_id] = l; });

    // Fixed positions for a cleaner layout (IEEE 13-bus specific)
    const positions = {
      0: { x: width * 0.1, y: height * 0.15 },     // Substation
      1: { x: width * 0.22, y: height * 0.15 },     // Bus 650
      2: { x: width * 0.4, y: height * 0.35 },      // Bus 632
      3: { x: width * 0.55, y: height * 0.2 },      // Bus 633
      4: { x: width * 0.68, y: height * 0.12 },     // Bus 634
      5: { x: width * 0.35, y: height * 0.6 },      // Bus 645
      6: { x: width * 0.25, y: height * 0.78 },     // Bus 646
      7: { x: width * 0.62, y: height * 0.52 },     // Bus 671
      8: { x: width * 0.75, y: height * 0.42 },     // Bus 692
      9: { x: width * 0.88, y: height * 0.32 },     // Bus 675
      10: { x: width * 0.72, y: height * 0.72 },    // Bus 611
      11: { x: width * 0.52, y: height * 0.82 },    // Bus 652
      12: { x: width * 0.85, y: height * 0.82 },    // Bus 680
    };

    // Assign positions to nodes
    const nodes = topology.nodes.map(n => ({
      ...n,
      x: positions[n.id]?.x || width / 2,
      y: positions[n.id]?.y || height / 2,
    }));

    const links = topology.edges.map(e => ({
      ...e,
      source: nodes.find(n => n.id === e.source),
      target: nodes.find(n => n.id === e.target),
    }));
    const edgePath = d => `M ${d.source.x} ${d.source.y} L ${d.target.x} ${d.target.y}`;

    // Glow filter
    const defs = svg.append('defs');
    const filter = defs.append('filter').attr('id', 'glow');
    filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur');
    const feMerge = filter.append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Highlight glow filter
    const highlightFilter = defs.append('filter').attr('id', 'highlight-glow');
    highlightFilter.append('feGaussianBlur').attr('stdDeviation', '5').attr('result', 'coloredBlur');
    const feMerge2 = highlightFilter.append('feMerge');
    feMerge2.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge2.append('feMergeNode').attr('in', 'SourceGraphic');

    // Draw feeder paths with an animated dashed overlay for the default current.
    svg.selectAll('.grid-line').remove();
    svg.selectAll('.grid-line')
      .data(links)
      .join('path')
      .attr('class', 'grid-line')
      .attr('d', edgePath)
      .attr('stroke', d => {
        const loading = lineLoadings[d.id] || 0;
        return getLoadingColor(loading);
      })
      .attr('stroke-width', d => {
        const loading = lineLoadings[d.id] || 0;
        return lineViolations.has(d.id) ? 4 : Math.max(2, loading / 30);
      })
      .attr('stroke-opacity', 0.7)
      .style('filter', d => lineViolations.has(d.id) ? 'url(#glow)' : 'none');

    const flowPaths = svg.selectAll('.current-flow')
      .data(links)
      .join('path')
      .attr('class', 'current-flow')
      .attr('d', edgePath)
      .attr('fill', 'none')
      .attr('stroke', 'var(--accent-blue)')
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '3 9')
      .attr('stroke-linecap', 'round')
      .attr('opacity', 0.65);

    // Bright moving particles make the default feeder direction visible without
    // hiding the congestion color underneath.
    svg.selectAll('.flow-particle')
      .data(links.flatMap(link => [link, link]))
      .join('circle')
      .attr('class', 'flow-particle')
      .attr('r', 2.5)
      .attr('fill', 'var(--accent-primary)')
      .attr('opacity', 0.95)
      .each(function (d, index) {
        const path = flowPaths.filter(link => link.id === d.id).node();
        if (!path) return;
        const particle = d3.select(this);
        const start = index % 2 === 0 ? 0 : 0.5;
        const move = () => {
          particle
            .attr('transform', `translate(${path.getPointAtLength(start * path.getTotalLength()).x},${path.getPointAtLength(start * path.getTotalLength()).y})`)
            .transition()
            .duration(2400)
            .ease(d3.easeLinear)
            .attrTween('transform', () => t => {
              const progress = start + (1 - start) * t;
              const point = path.getPointAtLength(progress * path.getTotalLength());
              return `translate(${point.x},${point.y})`;
            })
            .on('end', move);
        };
        move();
      });

    // Draw line loading labels
    svg.selectAll('.line-label')
      .data(links)
      .join('text')
      .attr('class', 'line-label')
      .attr('x', d => (d.source.x + d.target.x) / 2)
      .attr('y', d => (d.source.y + d.target.y) / 2 - 8)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--text-muted)')
      .attr('font-size', '9px')
      .attr('font-family', 'var(--font-mono)')
      .text(d => {
        const loading = lineLoadings[d.id];
        return loading ? `${loading.toFixed(0)}%` : '';
      });

    // Draw nodes
    const nodeGroups = svg.selectAll('.node-group')
      .data(nodes)
      .join('g')
      .attr('class', 'node-group')
      .attr('transform', d => `translate(${d.x}, ${d.y})`)
      .style('cursor', onBusClick ? 'pointer' : 'default')
      .on('click', (event, d) => {
        if (onBusClick) onBusClick(d.id);
      });

    // Node circles
    nodeGroups.append('circle')
      .attr('r', d => {
        if (d.id === highlightBus) return 18;
        if (d.type === 'substation') return 16;
        return 12;
      })
      .attr('fill', d => {
        if (d.id === highlightBus) return 'rgba(16, 185, 129, 0.3)';
        const v = busVoltages[d.id];
        if (v === undefined) return 'var(--bg-tertiary)';
        return getVoltageColor(v);
      })
      .attr('fill-opacity', d => d.id === highlightBus ? 0.4 : 0.25)
      .attr('stroke', d => {
        if (d.id === highlightBus) return 'var(--accent-green)';
        const v = busVoltages[d.id];
        if (v === undefined) return 'var(--border-medium)';
        return getVoltageColor(v);
      })
      .attr('stroke-width', d => {
        if (d.id === highlightBus) return 3;
        return busViolations.has(d.id) ? 3 : 1.5;
      })
      .style('filter', d => {
        if (d.id === highlightBus) return 'url(#highlight-glow)';
        return busViolations.has(d.id) ? 'url(#glow)' : 'none';
      })
      .style('transition', 'all 0.3s ease');

    // "YOU" label on highlighted bus
    if (highlightBus != null) {
      const highlightNode = nodes.find(n => n.id === highlightBus);
      if (highlightNode) {
        svg.append('text')
          .attr('x', highlightNode.x)
          .attr('y', highlightNode.y + 32)
          .attr('text-anchor', 'middle')
          .attr('fill', 'var(--accent-green)')
          .attr('font-size', '10px')
          .attr('font-weight', '700')
          .text('YOU');
      }
    }

    // Node labels
    nodeGroups.append('text')
      .attr('y', d => {
        if (d.id === highlightBus) return -24;
        return d.type === 'substation' ? 28 : 24;
      })
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--text-secondary)')
      .attr('font-size', '10px')
      .attr('font-weight', '500')
      .text(d => d.name.replace('Bus_', ''));

    // Voltage labels
    nodeGroups.append('text')
      .attr('y', d => d.id === highlightBus ? -36 : -18)
      .attr('text-anchor', 'middle')
      .attr('fill', d => {
        const v = busVoltages[d.id];
        return v ? getVoltageColor(v) : 'var(--text-muted)';
      })
      .attr('font-size', '9px')
      .attr('font-family', 'var(--font-mono)')
      .text(d => {
        const v = busVoltages[d.id];
        return v ? `${(v * 100).toFixed(1)}%` : '';
      });

    // Listing price tags (for buyer view)
    if (role === 'buyer' && listings.length > 0) {
      nodes.forEach(node => {
        const listing = listingByBus[node.id];
        if (listing) {
          const g = svg.append('g')
            .attr('transform', `translate(${node.x + 16}, ${node.y - 16})`)
            .style('cursor', 'pointer')
            .on('click', () => { if (onBusClick) onBusClick(node.id); });

          g.append('rect')
            .attr('rx', 4).attr('ry', 4)
            .attr('width', 50).attr('height', 20)
            .attr('fill', 'var(--accent-green-dim)')
            .attr('stroke', 'var(--accent-green)')
            .attr('stroke-width', 1);

          g.append('text')
            .attr('x', 25).attr('y', 14)
            .attr('text-anchor', 'middle')
            .attr('fill', 'var(--accent-green)')
            .attr('font-size', '9px')
            .attr('font-weight', '600')
            .attr('font-family', 'var(--font-mono)')
            .text(`₹${listing.asking_price_per_kwh.toFixed(1)}`);
        }
      });
    }

    // Listing indicators for seller view (show which buses have surplus)
    if (role === 'seller' && listings.length > 0) {
      nodes.forEach(node => {
        const listing = listingByBus[node.id];
        if (listing && node.id !== highlightBus) {
          svg.append('circle')
            .attr('cx', node.x + 14)
            .attr('cy', node.y - 14)
            .attr('r', 5)
            .attr('fill', 'var(--accent-blue)')
            .attr('stroke', 'var(--bg-primary)')
            .attr('stroke-width', 1.5);
        }
      });
    }

    // Legend
    const legend = svg.append('g').attr('transform', `translate(${width - 140}, ${height - 60})`);
    
    const legendItems = [
      { color: 'var(--accent-green)', label: 'Normal' },
      { color: 'var(--accent-amber)', label: 'Warning' },
      { color: 'var(--accent-red)', label: 'Violation' },
    ];

    legendItems.forEach((item, i) => {
      legend.append('circle')
        .attr('cx', 0)
        .attr('cy', i * 18)
        .attr('r', 5)
        .attr('fill', item.color)
        .attr('fill-opacity', 0.5)
        .attr('stroke', item.color);

      legend.append('text')
        .attr('x', 14)
        .attr('y', i * 18 + 4)
        .attr('fill', 'var(--text-muted)')
        .attr('font-size', '10px')
        .text(item.label);
    });

  }, [topology, gridState, highlightBus, listings, role]);

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">⚡ Grid Network Topology</span>
        <span className="text-xs text-muted">IEEE 13-Bus Test Feeder</span>
      </div>
      <div className="grid-viz-container">
        <svg ref={svgRef}></svg>
      </div>
    </div>
  );
}
