from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_scenario
from app.domain.scenario import Scenario
from app.schemas.version import VersionCreate, VersionSaved, VersionSummary
from app.versions_store import save_versions

router = APIRouter(prefix="/versions", tags=["versions"])

# Named versions (section 13). Saving and deleting change only the list of
# versions (they are not undoable actions) and are written to disk right
# away. Restoring replaces the scenario through load_scenario, so it IS an
# undoable action (POST /undo).


def _persist_or_rollback(scenario: Scenario, rollback) -> None:
    """Write the versions to disk. If writing fails, undo the in-memory
    change so memory and disk do not disagree, and answer 500."""
    try:
        save_versions(scenario.export_versions())
    except OSError as error:
        rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not write the versions file: {error}",
        ) from error


@router.get("", response_model=list[VersionSummary])
def list_versions(scenario: Scenario = Depends(get_scenario)):
    return scenario.version_summaries()


@router.post("", response_model=VersionSaved, status_code=status.HTTP_201_CREATED)
def save_version(data: VersionCreate, scenario: Scenario = Depends(get_scenario)):
    try:
        result = scenario.save_version(data.name)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    _persist_or_rollback(scenario, lambda: scenario.versions.pop(result["saved"], None))
    return result


@router.post("/{name}/restore")
def restore_version(name: str, scenario: Scenario = Depends(get_scenario)):
    """Same summary as POST /scenario/load, plus "restored_version"."""
    try:
        return scenario.restore_version(name)
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error.args[0]) if error.args else str(error),
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_version(name: str, scenario: Scenario = Depends(get_scenario)):
    if name not in scenario.versions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version '{name}' was not found")
    removed = scenario.versions[name]
    scenario.delete_version(name)
    _persist_or_rollback(scenario, lambda: scenario.versions.__setitem__(name, removed))
