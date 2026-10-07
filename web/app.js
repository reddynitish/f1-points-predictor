'use strict';
const data = JSON.parse(document.getElementById('dashboard-data').textContent);
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = value => String(value || 'Unavailable').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
const percent = p => `${(100 * p).toFixed(1)}%`;
const repo = 'https://github.com/reddynitish/f1-points-predictor';
const catalog = new Map(data.catalog.events.map(e => [e.event_id,e]));
const summary = data.replays.v1.summary;
const liveArchives = data.archives.filter(a => a.mode === 'prospective');
const utc = value => value ? `${value.replace('T',' ').slice(0,16)} UTC` : 'Unavailable';
function fillEvents(){
  const live = $('source').value === 'live';
  const ids = live ? liveArchives.map(a => a.event_id) : [...new Set(data.replays.v1.predictions.map(p => p.event_id))];
  $('event').innerHTML = ids.map(id => `<option value="${esc(id)}">R${Number(id.split('-')[1])} · ${esc(pretty(catalog.get(id)?.circuit_id || id))}</option>`).join('');
  $('event').disabled = !ids.length;
  $('empty').hidden = !!ids.length; $('event-view').hidden = !ids.length;
  if(ids.length){$('event').value=ids[ids.length-1];renderEvent();}
}
function renderEvent(){
  const id = $('event').value, live = $('source').value === 'live';
  const archive = live ? liveArchives.find(a => a.event_id===id) : null;
  const event = catalog.get(id) || {};
  const liveScore = data.scorecard.races.find(r => r.event_id===id);
  const outcomes = new Map((liveScore?.outcomes || []).map(r => [r.driver_id,r.scored_points]));
  const rows = live ? archive.predictions.map(r => ({...r,scored_points:outcomes.get(r.driver_id)})) : data.replays.v1.predictions.filter(p => p.event_id===id);
  const model = $('model').value, other = model === 'p_B1' ? 'p_M1' : 'p_B1';
  const score = live ? data.scorecard.races.find(r => r.event_id===id) : summary.per_race.find(r => r.event_id===id);
  const outcomeKnown = rows.every(r => r.scored_points===0 || r.scored_points===1);
  $('mode').textContent=live?'Prospective forecast':'Retrospective replay';
  $('mode').className=`badge ${live?'live':''}`;
  $('race-title').textContent=`${pretty(event.circuit_id || archive?.circuit_id || id)} · Round ${Number(id.split('-')[1])}`;
  $('race-meta').textContent=`${id} / ${rows.length} qualifying drivers${event.sprint_weekend?' / Sprint weekend':''}`;
  const metric = outcomeKnown ? rows.reduce((n,r)=>n+(r[model]-r.scored_points)**2,0)/rows.length : score?.[model==='p_B1'?'brier_B1':'brier_M1'];
  const hits = outcomeKnown ? [...rows].sort((a,b)=>b[model]-a[model]).slice(0,10).reduce((n,r)=>n+r.scored_points,0) : score?.top10_hits_B1;
  $('race-stats').innerHTML = `<div class="stat"><strong>${rows.length}</strong>Drivers covered</div><div class="stat"><strong>${metric == null?'Pending':metric.toFixed(3)}</strong>Brier score · lower is better</div><div class="stat"><strong>${hits == null?'Pending':`${hits} / ${Math.min(10,rows.length)}`}</strong>${outcomeKnown?'Correct top-10 picks':'B1 top-10 score'}</div>`;
  $('cutoff-note').textContent=live?'Archived before scheduled race start. Outcomes appear only when results cover every archived driver.':'Replay generated after these races. Historical qualifying uses retrieved classifications; exact publication/revision timing is not reconstructed.';
  $('drivers').innerHTML=[...rows].sort((a,b)=>b[model]-a[model]).map(r => {
    const known=r.scored_points===0||r.scored_points===1;
    return `<tr><td><span class="driver-name">${esc(pretty(r.driver_id))}</span><span class="team">${esc(pretty(r.constructor_id))}</span></td><td><span class="q-rank">${r.qualifying_rank == null?'Missing':`P${Number(r.qualifying_rank)}`}</span></td><td><div class="prob"><div class="lane" aria-hidden="true"><span style="width:${100*r[model]}%"></span></div><strong>${percent(r[model])}</strong></div></td><td class="secondary">${percent(r[other])}</td><td class="outcome ${known?(r.scored_points?'yes':'no'):''}">${known?(r.scored_points?'<span aria-hidden="true">●</span>Scored points':'<span aria-hidden="true">○</span>No points'):'Awaiting result'}</td></tr>`;
  }).join('');
  const metadata=archive||summary;
  const cutoff=archive?.cutoff||'Interval: scheduled qualifying start to race start';
  const info = [['Mode', live?'Prospective forecast':'Retrospective replay'],['Primary model','B1 · qualifying-rank logistic'],['Generated',utc(archive?.created_at || summary.generated_at)],['Scheduled qualifying',utc(archive?.qualifying_scheduled_start_utc || event.qualifying_scheduled_start_utc)],['Scheduled race',utc(archive?.race_start_utc || event.race_start_utc)],['Cutoff policy',cutoff],['Source commit',metadata.git_commit],['Config SHA-256',metadata.config_sha256]];
  $('provenance').innerHTML=`<dl>${info.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>${archive?.warnings?.length?`<ul>${archive.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul>`:'<p>Qualifying-row roster only; drivers absent from the qualifying endpoint are excluded. Historical classification revisions remain a limitation.</p>'}`;
}
function renderEvaluation(){
  const v2=data.replays.v2.summary, pre=data.replays.pre_race.summary;
  const models=[['B1 · Qualifying rank','Primary · qualifying cutoff',summary.metrics.B1.race_brier,true],['M1 · Driver / team history','Comparison · qualifying cutoff',summary.metrics.M1.race_brier],['M2 v2 · Practice / gap / weather','Comparison · qualifying cutoff',v2.metrics.M1.race_brier],['BG · Starting grid','Baseline · pre-race cutoff',pre.metrics.B1.race_brier],['M2 pre-race · Additional signals','Comparison · pre-race cutoff',pre.metrics.M1.race_brier]];
  $('comparison').innerHTML=models.map(([name,cutoff,value,primary])=>`<div class="comparison-row ${primary?'primary':''}"><span>${esc(name)}<small>${esc(cutoff)}</small></span><strong>${value.toFixed(3)}</strong></div>`).join('');
  const ci=summary.bootstrap_M1_vs_B1.difference_vs_p_B1.p_M1;
  $('interval').textContent=`M1 − B1: 95% whole-event bootstrap interval [${ci[0].toFixed(4)}, +${ci[1].toFixed(4)}]. It includes zero; improvement is inconclusive.`;
  const x=p=>48+p*260, y=p=>278-p*240;
  $('calibration').innerHTML=`<svg class="calibration-svg" viewBox="0 0 350 325" role="img" aria-label="Calibration chart: predicted probability versus observed scoring rate. Dashed line is perfect calibration. Exact bin values follow in an expandable table.">${[0,.25,.5,.75,1].map(p=>`<line x1="48" y1="${y(p)}" x2="308" y2="${y(p)}" stroke="#dce6ed"/><text x="38" y="${y(p)+3}" text-anchor="end">${p*100}%</text><text x="${x(p)}" y="297" text-anchor="middle">${p*100}%</text>`).join('')}<line x1="48" y1="278" x2="308" y2="38" stroke="#9b7a52" stroke-dasharray="4 5"/>${summary.reliability_B1.map(b=>`<circle cx="${x(b.mean_predicted)}" cy="${y(b.observed_rate)}" r="${4+Math.sqrt(b.count)/2}" fill="#166dad" stroke="white" stroke-width="2"><title>${percent(b.mean_predicted)} predicted; ${percent(b.observed_rate)} scored; n=${b.count}</title></circle>`).join('')}<text x="178" y="321" text-anchor="middle">Predicted chance of points</text><text x="48" y="19">Observed scoring rate</text></svg><details><summary>Exact calibration values and counts</summary><div class="table-scroll"><table class="ledger"><thead><tr><th>Predicted</th><th>Scored</th><th>Drivers</th></tr></thead><tbody>${summary.reliability_B1.map(b=>`<tr><td>${percent(b.mean_predicted)}</td><td>${percent(b.observed_rate)}</td><td>${b.count}</td></tr>`).join('')}</tbody></table></div></details>`;
  const errors=data.diagnostics;
  $('failure-copy').textContent=errors?`${errors.confident_misses.length} drivers given at least an 80% chance did not score. ${errors.low_probability_scorers.length} drivers given at most 20% did. Saved prediction errors show what happened; they do not prove why.`:'See the saved backtest for individual forecast errors.';
}
function renderHealth(){
  if(liveArchives.length){$('live-title').textContent=`${liveArchives.length} live forecast${liveArchives.length===1?'':'s'} archived`;$('live-copy').textContent=`${data.scorecard.races.length} scored races. Published before scheduled race start; results are kept separate from replays.`;}
  const h=data.health;
  if(!h){$('health').innerHTML='<p>No operational health snapshot has been published yet.</p><p class="small muted">Scheduled automation is configured. Successful live operation will be demonstrated by actual forecast archives and workflow diagnostics.</p>';return;}
  const age=(Date.now()-Date.parse(h.checked_at))/3600000;
  $('health').innerHTML=`<p><strong>${esc(pretty(h.status))}</strong> · last recorded check ${esc(utc(h.checked_at))}${age>6?' · snapshot older than six hours':''}</p><p class="small muted">Source fetched: ${esc(utc(h.source_fetched_at))}. Last recorded successful run: ${esc(utc(h.last_success_at))}.</p><ul class="health-list">${(h.events||[]).map(e=>`<li>${esc(e.event_id)} · ${esc(pretty(e.state))} · ${e.qualifying_drivers} qualifying / ${e.result_drivers} result drivers</li>`).join('')}</ul>${h.failures?.length?`<p class="notice">Collection failed: ${esc(h.failures.map(f=>`${f.stage}: ${f.error}`).join('; '))}</p>`:''}`;
}
$('source').addEventListener('change',fillEvents);$('event').addEventListener('change',renderEvent);$('model').addEventListener('change',renderEvent);
$('built').textContent=`Results snapshot ${utc(data.built_at)}`;
fillEvents();renderEvaluation();renderHealth();
