import { ReportFormValues } from '../../models/Report/ReportFormValues';
import ReportFormValidator from '../../components/reports/ReportFormValidator';

import Swal from 'sweetalert2';
import Breadcrumb from '../../components/Breadcrumb';
import { useNavigate } from "react-router-dom";


const CreateReport = () => {
    const navigate = useNavigate();

    // Creation logic
    const handleCreateReport = async (report: ReportFormValues) => {

        try {
            const createdReport = await reportService.createUser(report);
            if (createdReport) {
                Swal.fire({
                    title: "Completado",
                    text: "Se ha creado correctamente el reporte",
                    icon: "success",
                    timer: 3000
                })
                console.log("Reporte creado con éxito:", createdReport);
                navigate("/reportes/lista");
            } else {
                Swal.fire({
                    title: "Error",
                    text: "Existe un problema al momento de crear el reporte",
                    icon: "error",
                    timer: 3000
                })
            }
        } catch (error) {
            Swal.fire({
                title: "Error",
                text: "Existe un problema al momento de crear el reporte",
                icon: "error",
                timer: 3000
            })
        }
    };
    return (
        <div>
            {/* Form for report creation */}
            <h2>Crear reporte</h2>
            <Breadcrumb pageName="Crear reporte" />
            <ReportFormValidator
                handleAction={handleCreateReport}
                mode={1} // 1 stands for creation
                stations= {[]}
            />
        </div>
    );
};

export default CreateReport;

