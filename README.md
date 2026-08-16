# Athena

Athena is a Python application designed to collect, normalize, merge and analyze gaming activity from multiple platforms through a single data model.

The project was built around a simple idea: platform APIs expose different data structures, authentication methods and playtime formats, but the rest of the application should not need to know those platform-specific details. Athena therefore isolates external integrations in collectors and converts the collected data into reusable domain models before applying business logic.

## Main features

- Import gaming activity from several platforms.
- Normalize heterogeneous platform data into a common `NormalizedGame` model.
- Merge results from multiple sources while filtering invalid entries and duplicates.
- Calculate global statistics such as total playtime, average playtime, top games and platform distribution.
- Expose the same business services to both command-line and graphical workflows.
- Handle external API failures through controlled synchronization results instead of coupling error handling to the UI.

## Supported data sources

The repository currently contains integrations or import logic for:

- **Steam** — owned games and playtime through the Steam Web API.
- **osu!** — profile and playtime data through the osu! API.
- **Riot Games** — League of Legends and VALORANT collectors.
- **Epic Games** — local Epic-related collection logic.
- **Xbox** — import from normalized JSON data.

The graphical interface currently focuses on the Steam and osu! import flow, while additional collectors can be used or enabled from the application orchestration layer.

## Architecture

Athena follows a layered and reusable architecture:

```text
External platforms / local sources
              |
              v
         Collectors
              |
              v
      Normalized models
              |
              v
   Application services
   - ImportService
   - MergeService
   - StatsService
              |
       +------+------+
       |             |
       v             v
      CLI            UI
```

### Collectors

`collectors/` contains platform-specific integration logic. Each collector is responsible for authentication, remote requests, validation of external responses and conversion toward Athena-compatible data.

### Models

`models/` contains the domain objects shared by the application. `NormalizedGame` is the canonical representation used to describe a game independently of its original platform.

### Services

`services/` contains reusable business operations:

- `ImportService` coordinates data collection without depending on the presentation layer.
- `MergeService` consolidates results from several platforms.
- `StatsService` computes global statistics from normalized games.

The same services are reused by the CLI entry point and the graphical application.

### User interface

`ui/` contains the desktop interface built with **CustomTkinter**. The UI is separated into dedicated views for the home screen, statistics and the consolidated game library.

## Project structure

```text
Athena/
├── collectors/       # Platform-specific data collection
├── data/             # Local/imported application data
├── models/           # Shared domain models
├── repositories/     # Persistence abstractions
├── services/         # Reusable business services
├── tools/            # Quality and documentation utilities
├── ui/               # CustomTkinter graphical interface
├── utils/            # Shared utilities
├── main.py            # Command-line orchestration entry point
└── README.md
```

## Configuration

Sensitive credentials are intentionally kept outside version control. The local `config.py` file is ignored by Git and must contain the credentials and account identifiers required by the enabled collectors.

For the current graphical Steam and osu! flow, the main configuration values are:

```python
STEAM_API_KEY = "your_steam_api_key"
STEAM_ID = "your_steam_id"

OSU_CLIENT_ID = "your_osu_client_id"
OSU_CLIENT_SECRET = "your_osu_client_secret"
OSU_USER_ID = "your_osu_user_id"
```

Additional Riot or Epic settings can be added when those collectors are enabled.

Never commit real API keys or secrets to the repository.

## Running Athena

### Graphical interface

```bash
python ui/app.py
```

### Command-line workflow

```bash
python main.py
```

The command-line workflow imports configured platform data, merges the collected games and prints global statistics.

## Code quality

The codebase is structured to keep platform access, domain models, business logic and presentation responsibilities separate.

Ruff is used for automated static code checks, and the repository also contains `tools/documentation_ratio.py` to measure the proportion of internal documentation across production Python modules.

```bash
ruff check .
python tools/documentation_ratio.py
```

## Design principles

Athena is developed around the following principles:

- **Separation of concerns** — external APIs, business logic and presentation remain independent.
- **Reusability** — services and normalized models are shared by multiple entry points.
- **Extensibility** — a new gaming platform can be added through a collector without rewriting the statistics layer.
- **Maintainability** — explicit naming, internal documentation and static analysis are used to keep the code readable.
- **Safe configuration** — credentials remain outside the tracked source code.

## Project status

Athena is an evolving personal project used to experiment with multi-platform data integration, normalization and gaming activity analysis.
