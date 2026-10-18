// Deterministic force-directed layout for the knowledge graph view.
//
// A small Fruchterman–Reingold pass, sufficient for the bounded graphs
// the backend returns (≤150 nodes), with no layout library dependency.
// Initial positions come from a golden-angle spiral ordered by input
// index, so the same graph always lays out the same way. Disconnected
// nodes still repel, so they settle around the edge instead of piling up.

export interface LayoutNode {
  id: string;
}
export interface LayoutEdge {
  source: string;
  target: string;
}
export interface Point {
  x: number;
  y: number;
}

export function layoutGraph(
  nodes: LayoutNode[],
  edges: LayoutEdge[],
  width: number,
  height: number,
  iterations = 220,
): Map<string, Point> {
  const pos = new Map<string, Point>();
  const n = nodes.length;
  if (n === 0) return pos;

  const cx = width / 2;
  const cy = height / 2;
  const golden = Math.PI * (3 - Math.sqrt(5));
  const spread = Math.min(width, height) * 0.42;
  nodes.forEach((node, i) => {
    const r = spread * Math.sqrt((i + 0.5) / n);
    pos.set(node.id, { x: cx + r * Math.cos(i * golden), y: cy + r * Math.sin(i * golden) });
  });
  if (n === 1) return pos;

  const k = Math.sqrt((width * height) / n) * 0.75;
  const links = edges.filter((e) => pos.has(e.source) && pos.has(e.target) && e.source !== e.target);
  let temperature = Math.min(width, height) / 8;
  const cool = temperature / (iterations + 1);
  const ids = nodes.map((nd) => nd.id);

  for (let it = 0; it < iterations; it++) {
    const disp = new Map<string, Point>(ids.map((id) => [id, { x: 0, y: 0 }]));
    for (let i = 0; i < n; i++) {
      const a = pos.get(ids[i])!;
      for (let j = i + 1; j < n; j++) {
        const b = pos.get(ids[j])!;
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        let d = Math.hypot(dx, dy);
        if (d < 0.01) {
          dx = 0.01 * (i - j);
          dy = 0.01;
          d = Math.hypot(dx, dy);
        }
        const force = (k * k) / d;
        const da = disp.get(ids[i])!;
        const db = disp.get(ids[j])!;
        da.x += (dx / d) * force;
        da.y += (dy / d) * force;
        db.x -= (dx / d) * force;
        db.y -= (dy / d) * force;
      }
    }
    for (const e of links) {
      const a = pos.get(e.source)!;
      const b = pos.get(e.target)!;
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const d = Math.max(Math.hypot(dx, dy), 0.01);
      const force = (d * d) / k;
      const da = disp.get(e.source)!;
      const db = disp.get(e.target)!;
      da.x -= (dx / d) * force;
      da.y -= (dy / d) * force;
      db.x += (dx / d) * force;
      db.y += (dy / d) * force;
    }
    for (const id of ids) {
      const p = pos.get(id)!;
      const dv = disp.get(id)!;
      // Mild gravity keeps disconnected components on screen.
      dv.x += (cx - p.x) * 0.02 * k * 0.05;
      dv.y += (cy - p.y) * 0.02 * k * 0.05;
      const d = Math.max(Math.hypot(dv.x, dv.y), 0.01);
      const step = Math.min(d, temperature);
      p.x = Math.min(width - 24, Math.max(24, p.x + (dv.x / d) * step));
      p.y = Math.min(height - 24, Math.max(24, p.y + (dv.y / d) * step));
    }
    temperature -= cool;
  }
  return pos;
}
