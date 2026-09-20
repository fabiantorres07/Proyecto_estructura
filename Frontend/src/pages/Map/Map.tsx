import PlanoCartesiano from "../../components/map/Plano";

const Mapa = () => {
  return (
    <div className="min-h-screen w-full">
      <h2>Mapa de sismos</h2>

      <div className="h-[80vh] w-full">
        <PlanoCartesiano />
      </div>
    </div>
  );
};

export default Mapa;