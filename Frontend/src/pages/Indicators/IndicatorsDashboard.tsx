import IndicatorsTables from "../../components/indicators/IndicatorsTables";

const IndicatorsDashboard = () => (
    <main className="mx-auto max-w-screen-2xl space-y-6 p-4 md:p-6 2xl:p-8">
        <header className="border-b border-stroke pb-5">
            <h1 className="mt-1 text-2xl font-semibold text-black dark:text-white">Panel de indicadores</h1>
        </header>
        <IndicatorsTables />
    </main>
);

export default IndicatorsDashboard;
