import { useEffect, useState } from 'react';
import { Download, Upload, Undo2 } from 'lucide-react';
import Swal from 'sweetalert2';
import { clockService } from '../services/clockService';
import { getApiErrorMessage } from '../utils/utils';
import { modeService } from '../services/modeService';

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
    const loadMode = async () => {
      try {
        setStressMode(await modeService.getMode());
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

  const handleStressModeChange = async(value: boolean) => {
    setIsModeUpdating(true);
    try {
      await modeService.updateMode(value)
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
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded border border-stroke px-3 py-2 text-sm font-medium text-body hover:bg-gray dark:border-strokedark dark:text-bodydark dark:hover:bg-meta-4"
            >
              <Upload size={16} aria-hidden="true" />
              <span>Cargar versión</span>
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded border border-stroke px-3 py-2 text-sm font-medium text-body hover:bg-gray dark:border-strokedark dark:text-bodydark dark:hover:bg-meta-4"
            >
              <Download size={16} aria-hidden="true" />
              <span>Descargar versión</span>
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-2 rounded border border-stroke px-3 py-2 text-sm font-medium text-body hover:bg-gray dark:border-strokedark dark:text-bodydark dark:hover:bg-meta-4"
            >
              <Undo2 size={16} aria-hidden="true" />
              <span>Deshacer</span>
            </button>
          </div>

          <button
            type="button"
            role="switch"
            aria-checked={stressMode}
            disabled={isModeLoading || isModeUpdating}
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
