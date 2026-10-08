# NEXİS Dijital SEO/GEO Edge Backup

Date: 2026-10-08

This branch stores the SEO/GEO source deployed separately from the main website.

- Main production project: `nexis-dijital`
- Main production deployment preserved: `dpl_DqAq7Ak7ijeENVH3K3bimGsd6nod`
- Isolated SEO project: `nexis-seo-pages`
- SEO deployment: `dpl_7kUGXNfv5hZKMd2jGpzAU1UCKfj8`
- SEO origin: `seo.nexisdijital.com`
- Staged route version: `22a4aeb6-70a7-49cb-a217-5d551b3aa509`

Safety architecture: the original site files are not replaced. Only exact new SEO paths, sitemap.xml and llms.txt are routed to the isolated SEO project. Existing homepage, assets and service pages stay on the original deployment.

No credentials, passwords or secrets are stored here.
