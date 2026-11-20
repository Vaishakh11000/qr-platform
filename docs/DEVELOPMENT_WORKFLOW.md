# Platform Development Workflow

Develop the platform in coordinated increments across product and category management, QR management, regions and boundaries, public scans, location policies, analytics, audit logs, administration, and deployment. Prefer complete end-to-end workflows over polishing one module while another remains unusable.

## Admin usability and integration requirements

- Make every visible control perform a real action. Remove decorative buttons or connect them to their intended page or workflow.
- Keep global search useful across platform records and route results to the matching module.
- Keep the detailed, practical user guide behind “Need assistance? View documentation”; do not add a separate documentation navigation section. Explain catalogue, QR, region, policy, and form hierarchies, precedence, and known integration limits.
- Keep platform settings and integration status in Administration rather than duplicating them in the quick guide.
- Make notifications reflect real stored platform state. Label external email or push delivery as unavailable until a provider and its code integration are configured.
- Keep configurable service settings in Administration. When a feature needs a provider or deployment change, link to the relevant settings or setup guide and show what remains to be integrated.
- Do not mark an external integration as connected until credentials, implementation, and a real verification are complete.

## Verification and reporting

For each increment, list changed files, implemented behavior, commands and actual results, remaining limitations, and effects on other modules. Run the relevant frontend build/lint and backend tests when the available development environment supports them. Keep test and production databases separate, preserve the existing working tree, and do not change production records during development.

## Release workflow

Verify the product, QR, customer scan, administration/audit, and analytics workflows end to end before preparing deployment. Confirm persistent media, HTTPS, environment settings, backup/restore, logging, monitoring, and proxy protections. Record external dependencies that still need credentials or provider integration.
