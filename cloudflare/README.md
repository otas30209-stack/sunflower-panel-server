# Cloudflare D1 State Worker

Render cannot use Cloudflare D1 bindings directly. Use this Worker as a small token-protected bridge.

## Setup

1. Create a D1 database named `sunflower-panel-state`.
2. Run `schema.sql` on that database.
3. Deploy `d1-state-worker.js` with a D1 binding named `DB`.
4. Add a Worker secret named `STATE_TOKEN`.
5. Put these values in Render:
   - `D1_STATE_API_URL=https://your-worker.your-subdomain.workers.dev`
   - `D1_STATE_API_TOKEN=<same value as STATE_TOKEN>`

The Render server stores `users`, `licenses`, `notice`, `bot`, quick links and task config in this D1-backed state API.
