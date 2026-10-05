import { useCallback, useEffect, useState } from "react";
import Swal from "sweetalert2";
import Breadcrumb from "../../components/Breadcrumb";
import ReportFormValidator from "../../components/reports/ReportFormValidator";
import CartesianPlane from "../../components/map/Plane";
import { EventMapPoint } from "../../models/Event/EventMapPoint";
import { ReportFormValues } from "../../models/Report/ReportFormValues";
import { ReportReviewResponse } from "../../models/Report/ReportReviewResponse";
import { Station } from "../../models/Station";
import { Zone } from "../../models/Zone";
import { reportService } from "../../services/reportService";
import { stationService } from "../../services/stationService";
import { zoneService } from "../../services/zoneService";
import { getApiErrorMessage } from "../../utils/utils";

const ReportReviewNext = () => {
    const [review, setReview] = useState<ReportReviewResponse | null>(null);
    const [stations, setStations] = useState<Station[]>([]);
    const [zones, setZones] = useState<Zone[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadReview = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [nextReview, availableStations, availableZones] = await Promise.all([
                reportService.getNextReport(),
                stationService.getStations(),
                zoneService.getZones(),
            ]);
            setReview(nextReview);
            setStations(availableStations);
            setZones(availableZones);
            setHasUnsavedChanges(false);
        } catch (loadError) {
            setReview(null);
            setError(getApiErrorMessage(loadError, "No se pudo cargar el siguiente reporte"));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        void loadReview();
    }, [loadReview]);

    const updateReport = async (values: ReportFormValues) => {
        if (!review) return;
        setSaving(true);
        try {
            const updatedReport = await reportService.updateNextReport(values);
            setReview({ ...review, report: updatedReport });
            setHasUnsavedChanges(false);
            await Swal.fire({
                title: "Cambios guardados",
                text: "El reporte actualizado sigue al frente de la cola.",
                icon: "success",
                timer: 1800,
                showConfirmButton: false,
            });
        } catch (saveError) {
            await Swal.fire({
                title: "No se pudieron guardar los cambios",
                text: getApiErrorMessage(saveError, "Verifica los datos del reporte"),
                icon: "error",
            });
        } finally {
            setSaving(false);
        }
    };

    const processReport = async () => {
        if (!review) return;
        if (hasUnsavedChanges) {
            await Swal.fire({
                title: "Guarda los cambios primero",
                text: "El reporte en la cola todavía contiene los datos anteriores.",
                icon: "warning",
            });
            return;
        }
        const confirmation = await Swal.fire({
            title: "Aprobar reporte",
            text: `Se procesará el reporte de SIS-${review.report.event_id} y podrá crear o corregir el evento.`,
            icon: "question",
            showCancelButton: true,
            confirmButtonText: "Aprobar y procesar",
            cancelButtonText: "Volver",
        });
        if (!confirmation.isConfirmed) return;

        setSaving(true);
        try {
            const result = await reportService.processNextReport();
            await Swal.fire({
                title: "Reporte procesado",
                text: `${result.case} · SIS-${result.event_id} · revisión ${result.revision_num}`,
                icon: "success",
            });
            await loadReview();
        } catch (processError) {
            await Swal.fire({
                title: "No se pudo procesar el reporte",
                text: getApiErrorMessage(processError, "El reporte sigue en la cola"),
                icon: "error",
            });
        } finally {
            setSaving(false);
        }
    };

    const discardReport = async () => {
        if (!review) return;
        const confirmation = await Swal.fire({
            title: "Descartar reporte",
            text: `Se quitará SIS-${review.report.event_id} del frente de la cola sin modificar el evento.`,
            icon: "warning",
            showCancelButton: true,
            confirmButtonText: "Descartar",
            cancelButtonText: "Conservar",
        });
        if (!confirmation.isConfirmed) return;

        setSaving(true);
        try {
            await reportService.discardNextReport();
            await loadReview();
        } catch (discardError) {
            await Swal.fire({
                title: "No se pudo descartar el reporte",
                text: getApiErrorMessage(discardError, "El reporte sigue en la cola"),
                icon: "error",
            });
        } finally {
            setSaving(false);
        }
    };

    const report = review?.report;
    const currentEvent = review?.current_event;
    const eventMarker: EventMapPoint[] = report
        ? [{ event_id: report.event_id, x: report.x, y: report.y }]
        : [];
    const reportingStationIds = Array.from(new Set([
        ...(currentEvent?.stations ?? []),
        ...(report?.station_id ? [report.station_id] : []),
    ]));

    return (
        <main className="mx-auto max-w-screen-2xl space-y-6 p-4 md:p-6 2xl:p-8">
            <Breadcrumb pageName="Revisar siguiente reporte" />
            <header className="flex flex-wrap items-end justify-between gap-4 border-b border-stroke pb-5">
                <div>
                    <p className="text-sm font-medium uppercase text-meta-5">Frente de la cola</p>
                    <h1 className="mt-1 text-2xl font-semibold text-black">
                        {report ? `SIS-${report.event_id}` : "Revisar reporte"}
                    </h1>
                </div>
                {report && <span className="text-sm text-gray-500">Revisión {report.revision_num} · Estación {report.station_id}</span>}
            </header>

            {error && <p role="alert" className="border-l-4 border-danger bg-danger/5 px-4 py-3 text-danger">{error}</p>}
            {loading ? (
                <p className="py-10 text-center text-gray-500">Cargando reporte...</p>
            ) : !review || !report ? (
                <section className="border border-stroke bg-white px-6 py-12 text-center">
                    <h2 className="text-lg font-semibold text-black">No hay un reporte al frente</h2>
                    <p className="mt-2 text-sm text-gray-500">La cola está vacía o no se pudo encontrar el siguiente reporte.</p>
                </section>
            ) : (
                <>
                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                        <section className="space-y-4 border border-stroke bg-white p-5">
                            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stroke pb-4">
                                <div>
                                    <h2 className="text-lg font-semibold text-black">Evento vigente</h2>
                                    <p className="mt-1 text-sm text-gray-500">
                                        {review.current_event_status === "new" ? "Este ID no tiene un evento anterior." : `Estado: ${review.current_event_status}`}
                                    </p>
                                </div>
                            </div>
                            {currentEvent ? (
                                <dl className="grid grid-cols-2 gap-x-5 gap-y-4 text-sm">
                                    <div><dt className="text-gray-500">Magnitud</dt><dd className="mt-1 font-medium text-black">{currentEvent.magnitude.toFixed(1)}</dd></div>
                                    <div><dt className="text-gray-500">Profundidad</dt><dd className="mt-1 font-medium text-black">{currentEvent.depth.toFixed(1)} km</dd></div>
                                    <div><dt className="text-gray-500">Epicentro</dt><dd className="mt-1 font-medium text-black">({currentEvent.x.toFixed(1)}, {currentEvent.y.toFixed(1)})</dd></div>
                                    <div><dt className="text-gray-500">Ocurrencia</dt><dd className="mt-1 font-medium text-black">{new Date(currentEvent.occurred_at).toLocaleString()}</dd></div>
                                    <div><dt className="text-gray-500">Revisión</dt><dd className="mt-1 font-medium text-black">{currentEvent.revision}</dd></div>
                                    <div><dt className="text-gray-500">Estaciones aceptadas</dt><dd className="mt-1 font-medium text-black">{currentEvent.stations.join(", ") || "-"}</dd></div>
                                </dl>
                            ) : (
                                <p className="py-8 text-sm text-gray-500">{review.current_event_status === "deleted" ? "Este identificador fue eliminado y no puede crear un evento nuevo." : "Al aprobarlo, el reporte puede crear un evento nuevo."}</p>
                            )}
                        </section>

                        <section className="border border-stroke bg-white">
                            <header className="border-b border-stroke px-5 py-4">
                                <h2 className="text-lg font-semibold text-black">Datos del reporte</h2>
                                <p className="mt-1 text-sm text-gray-500">Edita los datos y guárdalos antes de aprobarlos.</p>
                            </header>
                            <ReportFormValidator
                                mode={3}
                                report={report}
                                stations={stations}
                                handleAction={updateReport}
                                onFormChange={() => setHasUnsavedChanges(true)}
                            />
                        </section>
                    </div>

                    <div className="flex flex-wrap justify-end gap-3 border-y border-stroke py-4">
                        <button type="button" disabled={saving} onClick={() => void discardReport()} className="border border-danger px-4 py-2.5 font-medium text-danger hover:bg-danger hover:text-white disabled:opacity-60">
                            Descartar reporte
                        </button>
                        <button type="button" disabled={saving || hasUnsavedChanges} onClick={() => void processReport()} className="bg-primary px-4 py-2.5 font-medium text-white hover:bg-opacity-90 disabled:opacity-60">
                            Aprobar y procesar
                        </button>
                    </div>
                    {hasUnsavedChanges && <p className="text-right text-sm text-warning">Guarda los cambios del reporte antes de aprobarlo.</p>}

                    <section className="space-y-3">
                        <div>
                            <h2 className="text-lg font-semibold text-black">Ubicación del reporte</h2>
                            <p className="mt-1 text-sm text-gray-500">Se muestran todas las estaciones y zonas; se resaltan las estaciones asociadas y el epicentro de este reporte.</p>
                        </div>
                        <div className="h-[60vh] min-h-96 w-full">
                            <CartesianPlane
                                stations={stations}
                                zones={zones}
                                events={eventMarker}
                                highlightedEventId={report.event_id}
                                highlightedStationIds={reportingStationIds}
                            />
                        </div>
                    </section>
                </>
            )}
        </main>
    );
};

export default ReportReviewNext;