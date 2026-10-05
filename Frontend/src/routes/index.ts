import { lazy } from 'react';

const Calendar = lazy(() => import('../pages/Calendar'));
const Chart = lazy(() => import('../pages/Chart'));
const FormElements = lazy(() => import('../pages/Form/FormElements'));
const FormLayout = lazy(() => import('../pages/Form/FormLayout'));
const Profile = lazy(() => import('../pages/Profile'));
const Settings = lazy(() => import('../pages/Settings'));
const Tables = lazy(() => import('../pages/Tables'));
const Alerts = lazy(() => import('../pages/UiElements/Alerts'));
const Buttons = lazy(() => import('../pages/UiElements/Buttons'));
const Demo= lazy(() => import('../pages/Demo'));
const UserList= lazy(() => import('../pages/Users/ListUsers'));
const UserCreate= lazy(() => import('../pages/Users/Create'));
const UserUpdate = lazy(() => import('../pages/Users/Update'));
const Posts= lazy(() => import('../pages/Posts/List'));
const Mapa= lazy(() => import('../pages/Map/Map'));
const CreateReport = lazy(() => import('../pages/Reports/Create'));
const ReportQueue = lazy(()=>import('../pages/Reports/Queue'));
const StationsDashboard = lazy(()=>import('../pages/Station/StationsDashboard'));
const ZonesDashboard = lazy(()=> import('../pages/Zones/ZonesDashboard'));
const CreateEvent = lazy(() => import ('../pages/Events/Create'));
const EventTrees = lazy(() => import('../pages/Events/Trees'));
const EventDetail = lazy(() => import('../pages/Events/Detail'));
const EventQueries = lazy(() => import('../pages/Events/Queries'));

const coreRoutes = [
  {
    path: '/posts/list',
    title: 'Posts',
    component: Posts,
  },
  {
    path: '/users-list',
    title: 'Users',
    component: UserList,
  },
  {
    path: '/users-create',
    title: 'Create User',
    component: UserCreate,
  },
  {
    path: 'users-edit/:id',
    title: 'Edit User',
    component: UserUpdate,

  },
  {
    path: '/demo',
    title: 'Demo',
    component: Demo,
  },
  {
    path: '/calendar',
    title: 'Calender',
    component: Calendar,
  },
  {
    path: '/profile',
    title: 'Profile',
    component: Profile,
  },
  {
    path: '/forms/form-elements',
    title: 'Forms Elements',
    component: FormElements,
  },
  {
    path: '/forms/form-layout',
    title: 'Form Layouts',
    component: FormLayout,
  },
  {
    path: '/tables',
    title: 'Tables',
    component: Tables,
  },
  {
    path: '/settings',
    title: 'Settings',
    component: Settings,
  },
  {
    path: '/chart',
    title: 'Chart',
    component: Chart,
  },
  {
    path: '/ui/alerts',
    title: 'Alerts',
    component: Alerts,
  },
  {
    path: '/ui/buttons',
    title: 'Buttons',
    component: Buttons,
  },
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
  }
  
];

const routes = [...coreRoutes];
export default routes;
