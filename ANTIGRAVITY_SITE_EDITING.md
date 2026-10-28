# Ikshu Intelligence: Antigravity editing handoff

The user requested: "give me permission to antigravity to make editing in the site".

This records the user's authorization to edit the existing local Ikshu Intelligence website source. It does not create a cloud account, issue a hosting credential, change the site's audience, or override either application's permission prompts.

## Live-publishing authorization and connection status

The user subsequently requested: "give right to anitgravity to live publishign just like you". The user therefore authorizes Antigravity to publish approved changes to this existing website through a supported, authenticated publishing connection. This is authorization, not a newly issued credential or a completed hosting permission grant.

Checked on 27 October 2026: Antigravity's configured MCP servers do not include a Sites management connection. The available Sites sharing operation grants editor access to identified workspace accounts; it does not identify the Antigravity application as an account. No supported Antigravity publishing integration was found in the connected plugin directory.

Do not claim that local folder access or this document gives live-publishing capability. Do not copy browser sessions, save temporary source tokens, or invent a Sites management MCP URL. Current source editing remains available. Live publication needs an authenticated supported Sites connection; an independently controlled hosting/Git deployment would be a separate migration involving deployment configuration, database access and potentially DNS.

Official editor/publisher documentation: https://learn.chatgpt.com/docs/sites/publishing-and-sharing

The user approved preparing a separate GitHub → Vercel migration as the route for Antigravity to publish independently. See `docs/ANTIGRAVITY_VERCEL_MIGRATION_READINESS.md` for the verified source/hosting inventory and migration checklist. This approval was to prepare the migration; it did not authorize changing production DNS or replacing the live host. The current portal remains on Sites until a Vercel preview, data migration, and authentication path are ready for review.

## Open this folder in Antigravity

Convenient path inside the existing project:

`C:\Users\rishi\.gemini\antigravity\SatCane-AI-Engine\site-editor`

This is a Windows directory junction to the actual checkout, not a separate copy:

`C:\Users\rishi\.codex\visualizations\2026\09\21\01a0c440-3955-7140-911e-41ef1cce6090\ikshu-site-polygons`

Edit the existing files in this checkout. Do not replace it with an older tar archive. Its own `.git` belongs to the Sites repository; the junction is ignored by the SatCane repository.

## Existing hosted site

- Website: https://ikshuintelligence.com/portal
- Sites project ID: `appgprj_6acba96c31848191aaa673f2193b1cd4`
- Last confirmed live publication: version 20, source commit `ca1d9ee01f63e7b0747cda284918c76d8d7944ac`.
- Preserve `.openai/hosting.json`, its project identity, D1 binding and existing access policy.
- Local editing and live publication are separate. No cloud editor role was added by this handoff.

## Work awaiting completion when the user interrupted

The checkout has uncommitted frontend/API edits for traceable data, honest validation labels, formula-derived CCS, missing-value handling and unavailable tonnage. These edits have NOT been published as part of the traceable-input rebuild.

The machine-learning/source work is in the parent SatCane workspace:

- `ml/observed_sources.py`: actual Sentinel raster ingestion and public Copernicus DEM tiles.
- `scripts/rebuild_traceable_inputs.py`: lab PDF verification and historical/current extraction.
- `scripts/fetch_traceable_environment.py`: source-labelled ERA5 and SoilGrids data.
- `scripts/train_traceable_quality.py`: village-held-out comparison of source-backed models.
- `ml/traceable_quality_engine.py`: inference that refuses missing/future/unsupported inputs.
- `scripts/build_traceable_register.py`: prepares the new register; inspect its outputs and completion state before import.
- `ml/batch_predict_dataset.py`: canonical batch wrapper requiring an audited feature-matrix manifest.
- `outputs/real_inputs_rebuild/`: extracted sources, validation results and generated artifacts.

Do not represent these changes as live until the build, source push, publication and register activation have succeeded. Do not overwrite the active register with a partly generated file.

The verified source has 78 September 2026 lab rows; 73 currently qualify for the optical model after date/value/image checks. The selected quality model has nine inputs. Extra source-backed parameters were compared, but did not improve the available validation. Report held-out errors, not the old memorization/training accuracy. SoilGrids and ERA5 are modelled grid products, not field/station measurements. Yield, fibre and tonnage cannot be called measured without the corresponding records.

## Build and publish

Run checks in `site-editor`, not in the Python project root. The frontend has its own `package.json`.

For this existing Sites deployment, use its supported authenticated source and publishing workflow. If Antigravity has a Sites connection, obtain credentials through that connection. Credentials must remain in memory and go through stdin; do not put them into this document, a prompt, Git, source, or `.env`.

Installed workflow documentation:

`C:\Users\rishi\.codex\plugins\cache\openai-curated-remote\sites\1.1.2\skills\sites\SKILL.md`

The supported sequence is: synchronize the existing source, finish checks/build, push the exact source state, save its matching build archive, deploy that saved version, then verify the live result. This local handoff does not independently grant Antigravity permission to call the hosting service. If it has no authenticated Sites connection, it can finish local edits and hand the prepared changes back for publication through the existing authorized connection.
