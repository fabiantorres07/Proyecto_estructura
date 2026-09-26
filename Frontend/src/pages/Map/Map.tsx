import CartesianPlane from "../../components/map/Plane";

const AppMap = () => {
  return (
    <div className="min-h-screen w-full">
      <h2>Mapa de sismos</h2>

      <div className="h-[80vh] w-full">
        <CartesianPlane />
      </div>
    </div>
  );
};

export default AppMap;