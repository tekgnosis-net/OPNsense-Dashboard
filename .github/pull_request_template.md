## What and why

## How it was tested

- [ ] `sh tests/run-static.sh`
- [ ] `sh tests/run-unit.sh`
- [ ] `sh tests/e2e/run.sh` (stack, provisioning or dashboard changes)
- [ ] On a real OPNsense router (router-side changes), version:

## Checklist

- [ ] Docs updated in this PR (README, docs/, CLAUDE.md as relevant)
- [ ] New or changed settings added to `.env.example` and the README settings table
- [ ] Dashboard JSON keeps `${dataSource}` / `${ESdataSource}` and `v.defaultBucket`
