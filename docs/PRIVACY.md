# Privacy & research-ethics boundary

This repository is a publicly shareable **synthetic-only demonstration**. GPS traces are highly identifying, even without names. Never ingest real device, patient, location-history, worker or student records here. Synthetic source labels are a self-declaration, not an assurance; stronger protections are needed for any future real-world use.

- Never log or commit API keys, PHI, actual location histories or real participant IDs.
- Production prerequisites: IRB/institutional approvals where applicable, consent, data-use agreements, threat model, access controls, audit logging, encryption, retention/deletion policy, approved hosting, robust deidentification and review of map tile calls.
- The page can load fonts and base tiles from external hosts. These requests may reveal IP addresses or map bounds. Leaflet code is served locally. Use `/?basemap=none` to disable remote map tiles.
- No security warranty, HIPAA compliance, health claims or validation claims in this demo.
