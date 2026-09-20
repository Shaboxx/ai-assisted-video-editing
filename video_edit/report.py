"""Inspectable, local review page. All displayed input is HTML escaped."""
from html import escape
from pathlib import Path


def write_page(directory: Path, plan: dict, report: dict, ingest: dict) -> None:
    rows = "".join(f"<tr><td>{index + 1:02d}</td><td>{span['start']:.3f}s</td><td>{span['end']:.3f}s</td>"
                   f"<td>{span['end'] - span['start']:.3f}s</td></tr>" for index, span in enumerate(plan["keep"]))
    lineage = "".join(f"<li><strong>{escape(field)}</strong> &larr; {escape(provider)}</li>"
                      for record in ingest["records"] for field, provider in record["field_sources"].items())
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AI-Assisted Video Editing · Review</title>
<style>
:root{{color-scheme:dark;--ink:#dce6ef;--dim:#9aaebf;--green:#40d6a4;--line:#26394b}}
*{{box-sizing:border-box}}body{{margin:0;background:#0b1421;color:var(--ink);font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1100px;margin:auto;padding:48px 24px 72px}}.eyebrow{{text-transform:uppercase;letter-spacing:.2em;color:var(--green);font-size:12px}}
h1{{font-size:clamp(32px,5vw,56px);line-height:1.1;letter-spacing:-.035em;margin:18px 0}}h2{{font-size:19px;margin:0 0 16px}}
.intro{{max-width:700px;color:var(--dim)}}.pill{{display:inline-block;color:#e9a557;border:1px solid #6b512f;border-radius:20px;padding:3px 12px;font-size:13px}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:30px 0}}.stat,.panel{{border:1px solid var(--line);border-radius:14px;background:#111e2d;padding:22px}}
.stat strong{{display:block;font-size:30px;color:var(--green)}}.stat span{{font-size:13px;color:var(--dim)}}
.videos,.detail{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:24px 0}}video{{width:100%;border-radius:8px;background:#000}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{text-align:left;padding:10px 5px;border-bottom:1px solid var(--line)}}th{{color:var(--dim)}}
a{{color:var(--green)}}code{{overflow-wrap:anywhere;color:#b8d8f0}}.note{{border-left:3px solid var(--green);padding:8px 18px;color:var(--dim)}}
small,footer{{color:var(--dim)}}footer{{font-size:13px;margin-top:40px}}@media(max-width:720px){{.videos,.detail{{grid-template-columns:1fr}}.stats{{gap:7px}}.stat{{padding:12px}}.stat strong{{font-size:24px}}}}
</style></head><body><main>
<div class="eyebrow">Local editing / evidence before export</div><h1>Remove the pauses.<br>Keep the reviewer.</h1>
<p class="intro">An inspectable editing proposal from a synthetic signal-and-pause video. Compare the source and preview, inspect the retained intervals, then approve this exact proposal in the CLI.</p>
<span class="pill">PROPOSED · awaiting human review</span>
<div class="stats"><div class="stat"><strong>{report['source_seconds']:.0f}s → {report['planned_output_seconds']:.2f}s</strong><span>Source to proposed edit</span></div>
<div class="stat"><strong>{report['signal_retention']:.1%}</strong><span>Synthetic signal retained</span></div>
<div class="stat"><strong>{len(plan['keep'])}</strong><span>Ordered intervals kept</span></div></div>
<div class="videos"><section class="panel"><h2>01 / Original synthetic source</h2><video controls preload="metadata" src="source-preview.mp4"></video><small>Green = tone. Amber = pause. Low-volume 440 Hz test tone; no speech.</small></section>
<section class="panel"><h2>02 / Proposed edit</h2><video controls preload="metadata" src="preview.mp4"></video><small>Review preview only. Final export requires a separate approval receipt.</small></section></div>
<div class="detail"><section class="panel"><h2>Source-coordinate edit plan</h2><table><thead><tr><th>Clip</th><th>Start</th><th>End</th><th>Duration</th></tr></thead><tbody>{rows}</tbody></table>
<p><a href="proposal.json">Proposal JSON</a> · <a href="report.json">Evaluation JSON</a></p></section>
<section class="panel"><h2>Ingestion you can trace</h2><p>{ingest['input_rows']} observations → {ingest['unique_assets']} asset; {ingest['duplicate_observations']} exact duplicate removed; {len(ingest['rejected_rows'])} invalid row rejected.</p><ul>{lineage}</ul>
<p>Conflicting non-empty metadata is retained in the conflict log. <a href="ingestion.json">Inspect all receipts</a>.</p></section></div>
<p class="note">This is a deterministic baseline, with no selected learned model. The fixture validates timing and review mechanics. It does not measure speech quality, storytelling, engagement, or editing judgment.</p>
<section class="panel"><h2>Review checklist</h2><p>Watch the preview with audio. Check each source interval, transitions, timing, and retained content. Approve only after reviewing; an approval is tied to the proposal hash and the original media hash.</p>
<p><code>python -m video_edit approve --workdir {escape(directory.name)} --reviewer "Your name" --note "Reviewed timing and content"</code></p>
<p><code>python -m video_edit export --workdir {escape(directory.name)}</code></p></section>
<footer>AI-Assisted Video Editing · Shawn Vazin · Synthetic demonstration, no external services</footer>
</main></body></html>'''
    (directory / "review.html").write_text(html, encoding="utf-8")
