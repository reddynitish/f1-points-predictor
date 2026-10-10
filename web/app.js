'use strict';
const data = JSON.parse(document.getElementById('dashboard-data').textContent);
const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pretty = value => String(value || 'Unknown').replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
const percent = p => `${(100 * p).toFixed(1)}%`;
const names = {albert_park:'Australian',shanghai:'Chinese',suzuka:'Japanese',miami:'Miami',villeneuve:'Canadian',monaco:'Monaco',catalunya:'Barcelona-Catalunya',red_bull_ring:'Austrian',silverstone:'British',spa:'Belgian',hungaroring:'Hungarian',zandvoort:'Dutch',monza:'Italian',madring:'Spanish',baku:'Azerbaijan',marina_bay:'Singapore',americas:'United States',rodriguez:'Mexico City',interlagos:'São Paulo',vegas:'Las Vegas',losail:'Qatar',yas_marina:'Abu Dhabi'};
const catalog = new Map(data.catalog.events.map(e => [e.event_id,e]));
const archives = data.archives.filter(a => a.mode === 'prospective' && a.pre_start_commit_verified).sort((a,b) => a.event_id.localeCompare(b.event_id));
const pastIds = [...new Set(data.replays.v1.predictions.map(p => p.event_id))];
const raceName = (id, archive) => `${names[(archive || catalog.get(id))?.circuit_id] || pretty((archive || catalog.get(id))?.circuit_id || id)} Grand Prix`;
const date = value => value ? new Date(value).toLocaleString(undefined,{month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}) : 'Time unavailable';
let showAll = false;
let currentRows = [];
let outcomesKnown = false;
function renderDrivers(){
  const rows = showAll ? currentRows : currentRows.slice(0,10);
  $('drivers').innerHTML=rows.map(r=>`<tr><td><span class="driver-name">${esc(pretty(r.driver_id))}</span>${r.qualifying_rank==null?'<span class="rank-caution">Qualifying position unknown</span>':''}</td><td><div class="probability"><span class="lane" aria-hidden="true"><span style="width:${100*r.p_B1}%"></span></span><strong>${percent(r.p_B1)}</strong></div></td>${outcomesKnown?`<td class="result ${r.scored_points?'yes':'no'}">${r.scored_points?'Yes':'No'}</td>`:''}</tr>`).join('');
  const more = $('more-drivers');
  more.hidden=currentRows.length<=10;
  more.textContent=showAll?'Show the top 10 only':`Show ${currentRows.length-10} more drivers`;
  more.setAttribute('aria-expanded',String(showAll));
}
function renderEvent(){
  showAll=false;
  const [type,id]=$('event').value.split(':');
  const live=type==='live';
  const archive=live?archives.find(a=>a.event_id===id):null;
  const event=archive || catalog.get(id) || {};
  const score=data.scorecard.races.find(r=>r.event_id===id);
  const outcomes=new Map((score?.outcomes || []).map(r=>[r.driver_id,r.scored_points]));
  currentRows=(live?(archive?.predictions || []).map(r=>({...r,scored_points:outcomes.get(r.driver_id)})):data.replays.v1.predictions.filter(r=>r.event_id===id)).sort((a,b)=>b.p_B1-a.p_B1 || String(a.driver_id).localeCompare(String(b.driver_id)));
  const available=!!currentRows.length;
  $('empty').hidden=available;
  $('event-view').hidden=!available;
  $('mode').textContent=live?'Saved before the race':'Past race example';
  $('mode').className=`badge ${live?'':'past'}`;
  if(!available){
    $('race-title').textContent='Waiting for a live prediction';
    $('race-meta').textContent='The next prediction needs published qualifying results.';
    $('mode').textContent='Not ready yet';
    $('selection-status').textContent='No live prediction is available.';
    return;
  }
  $('race-title').textContent=raceName(id,archive);
  $('race-meta').textContent=`${event.race_start_utc?`Race: ${date(event.race_start_utc)} · `:''}Round ${Number(id.split('-')[1])}`;
  outcomesKnown=currentRows.every(r=>r.scored_points===0||r.scored_points===1);
  $('result-heading').hidden=!outcomesKnown;
  $('race-note').textContent=live?(outcomesKnown?'Results are in. “Scored?” shows who earned race points.':'Highest chances first. We’ll check these against the race results.'):'These predictions were recreated after the race. They are examples, not live forecasts.';
  const missing=currentRows.filter(r=>r.qualifying_rank==null);
  $('rank-warning').hidden=!missing.length;
  $('rank-warning').textContent=`${missing.map(r=>pretty(r.driver_id)).join(', ')}: the qualifying position is unknown. Treat the estimate with extra caution.`;
  const details=[`Prediction saved: ${date(archive?.created_at || data.replays.v1.summary.generated_at)}.`,live?'It was committed before the scheduled race start.':'This is a past-race test, created afterward.',`Drivers covered: ${currentRows.length}. The list comes from qualifying results.`,`The main prediction uses qualifying position. Qualifying position can differ from the race starting grid.`,`Sunday race points only. Sprint points are excluded.`];
  $('prediction-details').innerHTML=details.map(text=>`<p>${esc(text)}</p>`).join('');
  const url=archive?.qualifying_source;
  if(typeof url==='string'&&/^https:\/\/www\.formula1\.com\//.test(url)){
    $('prediction-details').innerHTML+=`<p><a href="${esc(url)}">Official qualifying results</a> · read ${esc(date(archive.qualifying_retrieved_at))}. Later corrections may be included.</p>`;
  }
  $('prediction-details').innerHTML+='<p><a href="machine-learning.html#evidence">See how it was built and checked</a></p>';
  renderDrivers();
  $('selection-status').textContent=`${raceName(id,archive)}. ${live?'Saved live prediction':'Past race example'}. ${currentRows.length} drivers. ${outcomesKnown?'Results available.':'Race results pending.'}`;
}
const liveOptions=archives.map(a=>`<option value="live:${esc(a.event_id)}">${esc(raceName(a.event_id,a))} · ${a.event_id.split('-')[0]}</option>`).join('');
const pastOptions=pastIds.map(id=>`<option value="past:${esc(id)}">${esc(raceName(id))} · round ${Number(id.split('-')[1])}</option>`).join('');
$('event').innerHTML=`<optgroup label="Saved live predictions">${liveOptions||'<option value="live:none">Waiting for a live prediction</option>'}</optgroup><optgroup label="Past race examples">${pastOptions}</optgroup>`;
const upcoming=archives.find(a=>Date.parse(a.race_start_utc)>Date.now());
$('event').value=upcoming?`live:${upcoming.event_id}`:archives.length?`live:${archives[archives.length-1].event_id}`:'live:none';
$('event').addEventListener('change',()=>{$('prediction-details').parentElement.open=false;renderEvent();});
$('more-drivers').addEventListener('click',()=>{showAll=!showAll;renderDrivers();$('selection-status').textContent=showAll?`All ${currentRows.length} drivers shown.`:'Top 10 drivers shown.';});
renderEvent();

if(data.health && data.health.status!=='ok'){
  $('update-notice').hidden=false;
  $('update-notice').textContent='The latest data update failed. Saved predictions are still available. See Machine Learning for the current status.';
}
