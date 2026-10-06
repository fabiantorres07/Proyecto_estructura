import { lazy } from 'react';

const Mapa= lazy(() => import('../pages/Map/Map'));
const CreateReport = lazy(() => import('../pages/Reports/Create'));
const ReportQueue = lazy(()=>import('../pages/Reports/Queue'));
const ReviewNextReport = lazy(() => import('../pages/Reports/ReviewNext'));
const StationsDashboard = lazy(()=>import('../pages/Station/StationsDashboard'));
const ZonesDashboard = lazy(()=> import('../pages/Zones/ZonesDashboard'));
const CreateEvent = lazy(() => import ('../pages/Events/Create'));
const EventTrees = lazy(() => import('../pages/Events/Trees'));
const EventDetail = lazy(() => import('../pages/Events/Detail'));
const EventQueries = lazy(() => import('../pages/Events/Queries'));
const ParameterSettings = lazy(() => import('../pages/Parameters/ParameterSettings'));
const IndicatorsDashboard = lazy(() => import('../pages/Indicators/IndicatorsDashboard'));
const VersionsDashboard = lazy(() => import('../pages/Versions/VersionsDashboard'));

const coreRoutes = [

  {
    path: '/sismos/mapa',
    title: 'Mapa de sismos',
    component: Mapa,
  },
  {
    path: '/reportes/crear',
    title: 'Crear reporte',
    component: CreateReport,
  },
  {
    path: '/reportes/cola',
    title: 'Cola de reportes',
    component: ReportQueue,
  },
  {
    path: '/reportes/revisar',
    title: 'Revisar siguiente reporte',
    component: ReviewNextReport,
  },
  {
    path: '/estaciones/dashboard',
    title: 'Panel de estaciones',
    component: StationsDashboard,
  },
  {
    path: '/zonas/dashboard',
    title: 'Panel de zonas',
    component: ZonesDashboard,
  },
  {
    path: '/eventos/consultas',
    title: 'Consultas de eventos',
    component: EventQueries,
  },
  {
    path: '/eventos/arboles',
    title: 'Árboles de eventos',
    component: EventTrees,
  },
  {
    path: '/eventos/:eventId',
    title: 'Detalle del evento',
    component: EventDetail,
  },
  {
    path: '/eventos/crear',
    title: 'Creación de evento',
    component: CreateEvent,
  },
  {
    path: '/configuracion/parametros',
    title: 'Parámetros globales',
    component: ParameterSettings,
  },
  {
    path: '/indicadores',
    title: 'Panel de indicadores',
    component: IndicatorsDashboard,
  },
  {
    path: '/versiones',
    title: 'Versiones guardadas',
    component: VersionsDashboard,
  }
  
];

const routes = [...coreRoutes];
export default routes;
