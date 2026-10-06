import { TreeComparisonResponse } from "../../models/Event/TreeComparisonResponse";

interface TreeComparisonTableProps {
    comparison: TreeComparisonResponse;
}

const TreeComparisonTable: React.FC<TreeComparisonTableProps> = ({ comparison }) => (
    <section className="border border-stroke bg-white dark:border-strokedark dark:bg-boxdark">
        <header className="border-b border-stroke px-5 py-4 dark:border-strokedark">
            <h2 className="text-lg font-semibold text-black dark:text-white">Comparación AVL vs BST</h2>
            <p className="mt-1 text-sm text-gray-500">Búsquedas de las mismas {comparison.n_searches} claves.</p>
        </header>
        <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-left text-sm">
                <thead className="bg-gray-2 text-xs uppercase text-gray-600 dark:bg-meta-4 dark:text-bodydark2">
                    <tr>
                        <th className="px-5 py-3">Métrica</th>
                        <th className="px-5 py-3">AVL</th>
                        <th className="px-5 py-3">BST</th>
                    </tr>
                </thead>
                <tbody>
                    <tr className="border-t border-stroke dark:border-strokedark"><th className="px-5 py-3 font-medium">Altura</th><td className="px-5 py-3">{comparison.avl.height}</td><td className="px-5 py-3">{comparison.bst.height}</td></tr>
                    <tr className="border-t border-stroke dark:border-strokedark"><th className="px-5 py-3 font-medium">Hojas</th><td className="px-5 py-3">{comparison.avl.leaves}</td><td className="px-5 py-3">{comparison.bst.leaves}</td></tr>
                    <tr className="border-t border-stroke dark:border-strokedark"><th className="px-5 py-3 font-medium">Comparaciones totales</th><td className="px-5 py-3">{comparison.avl.total_comparisons}</td><td className="px-5 py-3">{comparison.bst.total_comparisons}</td></tr>
                    <tr className="border-t border-stroke dark:border-strokedark"><th className="px-5 py-3 font-medium">Máximo por búsqueda</th><td className="px-5 py-3">{comparison.avl.max_single_search}</td><td className="px-5 py-3">{comparison.bst.max_single_search}</td></tr>
                    <tr className="border-t border-stroke dark:border-strokedark"><th className="px-5 py-3 font-medium">Promedio por búsqueda</th><td className="px-5 py-3">{comparison.avl.avg_comparisons.toFixed(2)}</td><td className="px-5 py-3">{comparison.bst.avg_comparisons.toFixed(2)}</td></tr>
                </tbody>
            </table>
        </div>
    </section>
);

export default TreeComparisonTable;
