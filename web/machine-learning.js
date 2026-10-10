'use strict';
const data=JSON.parse(document.getElementById('dashboard-data').textContent);
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const date=value=>value?new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',year:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}):'Not recorded';
const summary=data.replays.v1.summary;
const hits=summary.per_race.map(r=>r.top10_hits_B1);
if(hits.length&&hits.every(Number.isFinite)){
  const average=hits.reduce((n,v)=>n+v,0)/hits.length;
  $('backtest-result').textContent=`Across ${hits.length} past races in 2026, an average of ${average.toFixed(1)} of the model’s 10 highest-chance picks scored points.`;
}
const archives=data.archives.filter(a=>a.mode==='prospective'&&a.pre_start_commit_verified);
const count=data.scorecard.races.length;
$('live-result').textContent=count?`${count} saved live ${count===1?'forecast has':'forecasts have'} now been checked against race results. You can see the results on the prediction page.`:archives.length?'The first live forecast has been saved. We still need the race result to check it.':'Live results are still pending. No saved live forecast has been scored yet.';
const comparisons=[['Qualifying position',summary],['Qualifying + practice and other information',data.replays.v2.summary],['Starting grid + other information',data.replays.pre_race.summary]];
$('comparison').innerHTML=comparisons.map(([label,s])=>`<tr><th scope="row">${esc(label)}</th><td>${s.metrics.B1.race_brier.toFixed(3)}</td><td>${s.metrics.M1.race_brier.toFixed(3)}</td></tr>`).join('');
const interval=summary.bootstrap_M1_vs_B1.difference_vs_p_B1.p_M1;
$('interval').textContent=`The estimate for the difference between the history model and the qualifying-only model ranges from ${interval[0].toFixed(4)} to ${interval[1].toFixed(4)} (95% interval, resampling whole races). Because that range includes zero, these results do not establish an improvement.`;
const repo='https://github.com/reddynitish/f1-points-predictor';
$('archive-proof').innerHTML=archives.length?archives.map(a=>{
  const filename=`${a.event_id}-prospective.json`;
  return `<p><a href="${repo}/blob/main/predictions/${encodeURIComponent(filename)}">${esc(a.event_id)}: full saved prediction</a><br><span class="small">Saved ${esc(date(a.created_at))}. First committed ${esc(date(a.archive_committed_at))}, before the scheduled race start. Git records the commit time; it does not independently verify when the public server received it.</span></p>`;
}).join(''):'<p>No verified live forecast has been saved yet.</p>';
const health=data.health;
const status=health?.status==='ok'?'The last recorded data check succeeded.':health?'A data or automation problem was recorded.':'No automation status has been saved yet.';
$('health').innerHTML=`<p>${esc(status)}</p>${health?.failures?.length?`<p class="note">${health.failures.map(f=>esc(`${f.stage}: ${f.error}`)).join('<br>')}</p>`:''}`;
$('built').textContent=`Data snapshot: ${date(data.built_at)}.`;
