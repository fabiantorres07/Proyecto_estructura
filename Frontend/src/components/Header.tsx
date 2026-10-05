import { ChangeEvent, useEffect, useRef, useState } from 'react';
import { Download, Upload, Undo2 } from 'lucide-react';
import Swal from 'sweetalert2';
import { clockService } from '../services/clockService';
import { getApiErrorMessage } from '../utils/utils';
import {
  MODE_STATE_UPDATED_EVENT,
  ModeStateUpdateEvent,
  modeService,
} from '../services/modeService';
import { undoService } from '../services/undoService';
import { scenarioService } from '../services/scenarioService';

const toLocalDateTime = (date: Date) =>
  new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 19);

const Header = (props: {
  sidebarOpen: string | boolean | undefined;
  setSidebarOpen: (arg0: boolean) => void;
}) => {
  const [dateTime, setDateTime] = useState('');
  const [isClockLoading, setIsClockLoading] = useState(true);
  const [isClockUpdating, setIsClockUpdating] = useState(false);
  const [stressMode, setStressMode] = useState(false);
  const [isModeLoading, setIsModeLoading] = useState(true);
  const [isModeUpdating, setIsModeUpdating] = useState(false);
  const [isAvlBalanced, setIsAvlBalanced] = useState(true);
  const [isUndoing, setIsUndoing] = useState(false);
  const [isScenarioBusy, setIsScenarioBusy] = useState(false);
  const scenarioFileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const loadClock = async () => {
      try {
        const clock = await clockService.getClock();
        setDateTime(toLocalDateTime(clock));
      } catch (error) {
        await Swal.fire({
          title: 'Error',
          text: getApiErrorMessage(error, 'No se pudo cargar el reloj'),
          icon: 'error',
        });
      } finally {
        setIsClockLoading(false);
      }
    };

    void loadClock();
  }, []);

  useEffect(() => {
    const syncModeState = (event: Event) => {
      const { stressMode: nextStressMode, isAvlBalanced: nextIsAvlBalanced } =
        (event as CustomEvent<ModeStateUpdateEvent>).detail;
      setStressMode(nextStressMode);
      setIsAvlBalanced(nextIsAvlBalanced);
    };

    window.addEventListener(MODE_STATE_UPDATED_EVENT, syncModeState);
    return () => window.removeEventListener(MODE_STATE_UPDATED_EVENT, syncModeState);
  }, []);

  useEffect(() => {
    const loadMode = async () => {
      try {
        const [loadedMode, audit] = await Promise.all([
          modeService.getMode(),
          modeService.getStructureAudit(),
        ]);
        setStressMode(loadedMode);
        setIsAvlBalanced(audit.is_valid && audit.is_avl);
      } catch (error) {
        await Swal.fire({
          title: 'Error',
          text: getApiErrorMessage(error, 'No se pudo cargar el modo'),
          icon: 'error',
        });
      } finally {
        setIsModeLoading(false);
      }
    };

    void loadMode();
  }, []);

  useEffect(() => {
    if (isClockLoading || isClockUpdating) {
      return;
    }

    const interval = window.setInterval(() => {
      setDateTime((currentDateTime) => {
        const currentTimestamp = Date.parse(currentDateTime);
        return Number.isNaN(currentTimestamp)
          ? currentDateTime
          : toLocalDateTime(new Date(currentTimestamp + 1000));
      });
    }, 1000);

    return () => window.clearInterval(interval);
  }, [isClockLoading, isClockUpdating]);

  const handleDateTimeChange = async (value: string) => {
    setDateTime(value);
    const updatedClock = new Date(value);

    if (!value || Number.isNaN(updatedClock.getTime())) {
      return;
    }

    setIsClockUpdating(true);
    try {
      await clockService.updateClock(updatedClock);
      const confirmedClock = await clockService.getClock();
      setDateTime(toLocalDateTime(confirmedClock));
    } catch (error) {
      await Swal.fire({
        title: 'Error',
        text: getApiErrorMessage(error, 'No se pudo actualizar el reloj'),
        icon: 'error',
      });
    } finally {
      setIsClockUpdating(false);
    }
  };

  const handleStressModeChange = async (value: boolean) => {
    setIsModeUpdating(true);
    try {
      if (stressMode && !value) {
        const audit = await modeService.getStructureAudit();
        const balanced = audit.is_valid && audit.is_avl;
        setIsAvlBalanced(balanced);
        if (!balanced) {
          await Swal.fire({
            title: 'AVL desbalanceado',
            text: 'Recupera el balance del árbol antes de desactivar el modo estrés.',
            icon: 'warning',
          });
          return;
        }
      }

      await modeService.updateMode(value);
      setStressMode(value);
    } catch (error) {
      await Swal.fire({
        title: 'Error',
        text: getApiErrorMessage(error, 'No se pudo actualizar el modo'),
        icon: 'error',
      })
    } finally {
      setIsModeUpdating(false);
    }
  }

  const handleUndo = async () => {
    setIsUndoing(true);
    try {
      const result = await undoService.undo();
      const [clock, stress, audit] = await Promise.all([
        clockService.getClock(),
        modeService.getMode(),
        modeService.getStructureAudit(),
      ]);
      setDateTime(toLocalDateTime(clock));
      setStressMode(stress);
      setIsAvlBalanced(audit.is_valid && audit.is_avl);

      const descriptions: Record<string, string> = {
        creation: 'creación',
        correction: 'corrección',
        reactivation: 'reactivación',
        deletion: 'eliminación',
        attention_change: 'cambio de atención',
        parameter_change: 'cambio de parámetro',
        clock_advance: 'avance del reloj',
        queue_step: 'paso de cola',
        mass_archive: 'archivo masivo',
        global_recovery: 'recuperación global',
        load: 'carga de escenario',
      };
      const target = result.event_id != null
        ? ` · SIS-${result.event_id}`
        : result.parameter ? ` · ${result.parameter}`
          : result.root_id != null ? ` · raíz SIS-${result.root_id}` : '';
      await Swal.fire({
        title: 'Acción deshecha',
        text: `${descriptions[result.undone] ?? result.undone}${target}`,
        icon: 'success',
      });
    } catch (error) {
      await Swal.fire({
        title: 'No se pudo deshacer',
        text: getApiErrorMessage(error, 'No hay acciones disponibles para deshacer'),
        icon: 'error',
      });
    } finally {
      setIsUndoing(false);
    }
  };

  const handleExportScenario = async () => {
    const selection = await Swal.fire({
      title: 'Formato de exportación',
      text: 'Topología conserva la estructura completa. Inserciones exporta solo eventos activos y reconstruye los árboles al cargarlos.',
      input: 'select',
      inputOptions: {
        topology: 'Topología completa',
        insertions: 'Por inserciones',
      },
      inputValue: 'topology',
      showCancelButton: true,
      confirmButtonText: 'Descargar',
      cancelButtonText: 'Cancelar',
    });
    if (!selection.isConfirmed || (selection.value !== 'insertions' && selection.value !== 'topology')) return;

    setIsScenarioBusy(true);
    try {
      const scenario = await scenarioService.exportScenario(selection.value);
      const file = new Blob([JSON.stringify(scenario, null, 2)], { type: 'application/json' });
      const downloadUrl = URL.createObjectURL(file);
      const link = document.createElement('a');
      link.href = downloadUrl;
      link.download = `sismolab-${selection.value}-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
      link.click();
      URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      await Swal.fire({
        title: 'Error al exportar',
        text: getApiErrorMessage(error, 'No se pudo descargar la simulación'),
        icon: 'error',
      });
    } finally {
      setIsScenarioBusy(false);
    }
  };

  const handleImportScenario = async (event: ChangeEvent<HTMLInputElement>) => {
    const input = event.currentTarget;
    const file = input.files?.[0];
    if (!file) return;

    setIsScenarioBusy(true);
    try {
      const parsed: unknown = JSON.parse(await file.text());
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        throw new Error('El archivo debe contener un objeto JSON de simulación.');
      }

      const detectedMode = (parsed as Record<string, unknown>).load_mode;
      const defaultMode = detectedMode === 'insertions' ? 'insertions' : 'topology';
      const confirmation = await Swal.fire({
        title: 'Formato de carga',
        text: 'La simulación actual será reemplazada. Inserciones reconstruye los árboles desde la lista de eventos; topología restaura el árbol guardado.',
        input: 'select',
        inputOptions: {
          insertions: 'Por inserciones',
          topology: 'Topología completa',
        },
        inputValue: defaultMode,
        showCancelButton: true,
        confirmButtonText: 'Cargar versión',
        cancelButtonText: 'Cancelar',
      });
      if (!confirmation.isConfirmed || (confirmation.value !== 'insertions' && confirmation.value !== 'topology')) return;

      const selectedMode = confirmation.value;
      const result = await scenarioService.loadScenario({
        ...(parsed as Record<string, unknown>),
        load_mode: selectedMode,
      });
      const [clock, stress, audit] = await Promise.all([
        clockService.getClock(),
        modeService.getMode(),
        modeService.getStructureAudit(),
      ]);
      setDateTime(toLocalDateTime(clock));
      setStressMode(stress);
      setIsAvlBalanced(audit.is_valid && audit.is_avl);

      const warnings = result.warnings.length ? ` Avisos: ${result.warnings.join('; ')}.` : '';
      await Swal.fire({
        title: 'Versión cargada',
        text: `${selectedMode === 'insertions' ? 'Por inserciones. ' : 'Por topología. '}${result.active_events} eventos activos, ${result.archived_events} archivados y ${result.queued_reports} reportes en cola.${warnings}`,
        icon: 'success',
      });
      window.location.reload();
    } catch (error) {
      await Swal.fire({
        title: 'No se pudo cargar la versión',
        text: getApiErrorMessage(error, 'El archivo no es válido o el backend no está disponible.'),
        icon: 'error',
      });
    } finally {
      input.value = '';
      setIsScenarioBusy(false);
    }
  };

  return (
    <header className="sticky top-0 z-999 flex w-full bg-white drop-shadow-1 dark:bg-boxdark dark:drop-shadow-none">
      <div className="flex w-full flex-wrap items-center gap-4 px-4 py-3 shadow-2 md:px-6 2xl:px-11">
        <div className="flex items-center lg:hidden">
          <button
            aria-controls="sidebar"
            aria-label="Abrir o cerrar menú"
            onClick={(e) => {
              e.stopPropagation();
              props.setSidebarOpen(!props.sidebarOpen);
            }}
            className="z-99999 block rounded-sm border border-stroke bg-white p-1.5 shadow-sm dark:border-strokedark dark:bg-boxdark"
          >
            <span className="relative block h-5.5 w-5.5 cursor-pointer">
              <span className="du-block absolute right-0 h-full w-full">
                <span
                  className={`relative top-0 left-0 my-1 block h-0.5 w-0 rounded-sm bg-black delay-[0] duration-200 ease-in-out dark:bg-white ${
                    !props.sidebarOpen && '!w-full delay-300'
                  }`}
                ></span>
                <span
                  className={`relative top-0 left-0 my-1 block h-0.5 w-0 rounded-sm bg-black delay-150 duration-200 ease-in-out dark:bg-white ${
                    !props.sidebarOpen && 'delay-400 !w-full'
                  }`}
                ></span>
                <span
                  className={`relative top-0 left-0 my-1 block h-0.5 w-0 rounded-sm bg-black delay-200 duration-200 ease-in-out dark:bg-white ${
                    !props.sidebarOpen && '!w-full delay-500'
                  }`}
                ></span>
              </span>
              <span className="absolute right-0 h-full w-full rotate-45">
                <span
                  className={`absolute left-2.5 top-0 block h-full w-0.5 rounded-sm bg-black delay-300 duration-200 ease-in-out dark:bg-white ${
                    !props.sidebarOpen && '!h-0 !delay-[0]'
                  }`}
                ></span>
                <span
                  className={`delay-400 absolute left-0 top-2.5 block h-0.5 w-full rounded-sm bg-black duration-200 ease-in-out dark:bg-white ${
                    !props.sidebarOpen && '!h-0 !delay-200'
                  }`}
                ></span>
              </span>
            </span>
          </button>
        </div>

        <div className="flex min-w-0 flex-1 flex-wrap items-center justify-end gap-3">
          <label className="flex min-w-0 items-center gap-2 text-sm font-medium text-body dark:text-bodydark">
            <span className="hidden md:inline">Fecha y hora</span>
            <input
              aria-label="Fecha y hora actual, editable hasta segundos"
              type="datetime-local"
              step="1"
              value={dateTime}
              disabled={isClockLoading || isClockUpdating}
              onChange={(event) => void handleDateTimeChange(event.target.value)}
              className="min-w-0 rounded border border-stroke bg-white px-2 py-2 text-sm text-black focus:border-primary focus:outline-none dark:border-strokedark dark:bg-boxdark dark:text-white"
            />
          </label>

          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={scenarioFileInput}
              type="file"
              accept="application/json,.json"
              className="sr-only"
              aria-label="Seleccionar archivo JSON de simulación"
              onChange={(event) => void handleImportScenario(event)}
            />
            <button
              type="button"
              disabled={isScenarioBusy}
              onClick={() => scenarioFileInput.current?.click()}
              className="inline-flex items-center gap-2 rounded border border-stroke px-3 py-2 text-sm font-medium text-body hover:bg-gray dark:border-strokedark dark:text-bodydark dark:hover:bg-meta-4"
            >
              <Upload size={16} aria-hidden="true" />
              <span>{isScenarioBusy ? 'Procesando...' : 'Cargar versión'}</span>
            </button>
            <button
              type="button"
              disabled={isScenarioBusy}
              onClick={() => void handleExportScenario()}
              className="inline-flex items-center gap-2 rounded border border-stroke px-3 py-2 text-sm font-medium text-body hover:bg-gray dark:border-strokedark dark:text-bodydark dark:hover:bg-meta-4"
            >
              <Download size={16} aria-hidden="true" />
              <span>Descargar versión</span>
            </button>
            <button
              type="button"
              disabled={isUndoing}
              onClick={() => void handleUndo()}
              className="inline-flex items-center gap-2 rounded border border-stroke px-3 py-2 text-sm font-medium text-body hover:bg-gray dark:border-strokedark dark:text-bodydark dark:hover:bg-meta-4"
            >
              <Undo2 size={16} aria-hidden="true" />
              <span>{isUndoing ? 'Deshaciendo...' : 'Deshacer'}</span>
            </button>
          </div>

          <button
            type="button"
            role="switch"
            aria-checked={stressMode}
            disabled={isModeLoading || isModeUpdating || (stressMode && !isAvlBalanced)}
            onClick={() => void handleStressModeChange(!stressMode)}
            className="inline-flex items-center gap-2 rounded px-2 py-2 text-sm font-medium text-body disabled:cursor-wait disabled:opacity-60 dark:text-bodydark"
          >
            <span>Modo estrés</span>
            <span
              className={`relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors ${stressMode ? "bg-primary" : "bg-bodydark2"}`}
            >
              <span
                className={`pointer-events-none absolute left-0.5 top-0.5 h-5 w-5 rounded-full bg-white transition-transform duration-200 ${stressMode ? "translate-x-5" : "translate-x-0"}`}
              />
            </span>
            <span className="w-7 text-left text-xs">{stressMode ? "On" : "Off"}</span>
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
