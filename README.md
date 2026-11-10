# Sotrama

Algerian localization and operational extensions for Frappe, ERPNext and Frappe HRMS, designed for public works, construction, quarrying, mining, transport and services.

> **Status:** foundation in progress. Payroll rules and declarations are not production-approved until their legal sources, effective dates and test cases have been reviewed.

## Scope

Sotrama is an independently installable Frappe app. It extends compatible ERPNext and HRMS sites through supported hooks, DocTypes, reports, fixtures and APIs. It does not fork or patch their source code.

## Development

See [Architecture](docs/ARCHITECTURE.md), [Project context](docs/PROJECT_CONTEXT.md), [Roadmap](docs/ROADMAP.md) and [Legal sources](docs/LEGAL_SOURCES.md). The app requires a Frappe bench and a site with compatible ERPNext and HRMS apps for integration tests.

```bash
bench get-app sotrama https://github.com/aa790933/sotrama.git
bench --site your-site install-app sotrama
bench --site your-site migrate
```

The commands above describe the intended installation flow; compatibility is not yet certified. See the compatibility matrix in the documentation.

## License

AGPL-3.0-only. See [LICENSE](LICENSE).
