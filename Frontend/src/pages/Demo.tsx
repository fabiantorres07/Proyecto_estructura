import { useState, useEffect } from "react";

export default function Demo() {


  useEffect(() => {//useEffect es llamar al método una vez se carga la página (DOMContentLoaded())
    console.log("Se cargó la página");
  }, []);

  return <p>Hola mundo</p>;
}
