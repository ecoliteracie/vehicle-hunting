# vehicle-hunting

A static comparison site for car shopping — pick a make, then a model, and see
every trim's price, efficiency, and full feature matrix on one page, with
charts so the differences are clear at a glance. Toyota only for now; built to
extend to other makes later.

**[Live site](https://ecoliteracie.github.io/vehicle-hunting/)** (once GitHub
Pages is enabled — see below).

## Structure

```
index.html          Page shell, header (make selector + theme toggle)
styles.css           Design tokens (light/dark) and all component styles
app.js                Hash router, rendering, table sort/search, Chart.js charts
data/vehicles.json    Structured trim data for every model — the site's source of truth
vehicle-profile/      Original per-vehicle markdown research notes (kept for provenance;
                       data/vehicles.json is hand-transcribed from these)
```

No build step, no framework, no dependencies beyond two free CDN includes
(Google Fonts "Inter" and Chart.js). Open `index.html` through a local server
(not `file://` — the JSON fetch needs http) or just visit the deployed site.

## Adding or updating a vehicle

1. Add a new `vehicle-profile/*.md` file (or edit an existing one) following
   the format of the others: lineup table, powertrain table, standard
   equipment, a feature matrix table, grade highlights, sources.
2. Hand-add/update the matching entry in `data/vehicles.json`. Each vehicle
   object needs: `id`, `make`, `model`, `modelSlug`, `year`, `bodyType`,
   `title`, `scope`, `researched`, `sourceFile`, `trims[]`, `powertrains[]`,
   `standardEquipment[]`, `featureMatrix` ({grades[], rows[]}), `sources[]`,
   and optionally `highlights[]` / `progression[]` / `specialEditions[]` /
   `notes[]` / `powertrainNotes[]`.
   - Every `trims[].grade` must appear in `featureMatrix.grades`.
   - Every `featureMatrix.rows[].values` array must be the same length as
     `featureMatrix.grades`.
   - Only give a trim its own priced row if the source states a distinct
     MSRP for it (e.g. a separately priced AWD variant). If AWD/etc. is just
     "available" with no separate price, add `awdAvailable: true` and an
     optional `awdNote` string instead of fabricating a row.
3. A new `modelSlug` automatically gets its own card on the home page; a
   model with more than one `year` profile automatically gets year tabs.

## Running locally

```bash
node -e "require('http').createServer((req,res)=>{const fs=require('fs'),path=require('path');let p=decodeURIComponent(req.url.split('?')[0]);if(p==='/')p='/index.html';const f=path.join(process.cwd(),p);fs.readFile(f,(e,d)=>{if(e){res.writeHead(404);res.end('not found')}else{res.writeHead(200);res.end(d)}})}).listen(8000,()=>console.log('http://localhost:8000'))"
```

Any static file server works equally well (`npx serve`, `python -m http.server`, etc).

## Deploying (GitHub Pages)

Settings → Pages → Source: **Deploy from a branch** → Branch: **main**, folder **/(root)**.
The site is plain static files at the repo root, so no build step or workflow is needed.
