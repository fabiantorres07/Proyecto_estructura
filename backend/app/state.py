from app.domain.scenario import Scenario
from app.versions_store import load_versions

scenario = Scenario()

# Named versions persist on disk (section 13): load them at startup.
scenario.import_versions(load_versions())