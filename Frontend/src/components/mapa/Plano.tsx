import { useEffect, useRef, useState } from "react";
import { Stage, Layer, Line, Text } from "react-konva";
import Zona from "./Zona";
import Evento from "./Evento";
function PlanoCartesiano() {
  const containerRef = useRef<HTMLDivElement>(null);

  const [size, setSize] = useState({
    width: 0,
    height: 0,
  });

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;

      setSize({
        width: width * 0.9,
        height: height * 0.9,
      });
    });

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  const { width, height } = size;

  const margen = 50;
  const escala = 40;

  const origenX = margen;
  const origenY = height - margen;

  return (
    <div ref={containerRef} className="w-full h-full">
      <Stage width={width} height={height}>
        <Layer>

          {/* CUADRÍCULA VERTICAL */}
          {Array.from(
            { length: Math.floor((width - margen) / escala) + 1 },
            (_, i) => {
              const x = origenX + i * escala;

              return (
                <Line
                  key={`vertical-${i}`}
                  points={[x, 0, x, origenY]}
                  stroke="#ddd"
                  strokeWidth={1}
                />
              );
            }
          )}

          {/* CUADRÍCULA HORIZONTAL */}
          {Array.from(
            { length: Math.floor((height - margen) / escala) + 1 },
            (_, i) => {
              const y = origenY - i * escala;

              return (
                <Line
                  key={`horizontal-${i}`}
                  points={[origenX, y, width, y]}
                  stroke="#ddd"
                  strokeWidth={1}
                />
              );
            }
          )}

          {/* EJE X */}
          <Line
            points={[origenX, origenY, width, origenY]}
            stroke="black"
            strokeWidth={2}
          />

          {/* EJE Y */}
          <Line
            points={[origenX, origenY, origenX, 0]}
            stroke="black"
            strokeWidth={2}
          />

          {/* NÚMEROS DEL EJE X */}
          {Array.from(
            { length: Math.floor((width - margen) / escala) + 1 },
            (_, i) => (
              <Text
                key={`x-label-${i}`}
                x={origenX + i * escala - 5}
                y={origenY + 8}
                text={String(i)}
                fontSize={14}
              />
            )
          )}

          {/* NÚMEROS DEL EJE Y */}
          {Array.from(
            { length: Math.floor((height - margen) / escala) + 1 },
            (_, i) => (
              <Text
                key={`y-label-${i}`}
                x={origenX - 25}
                y={origenY - i * escala - 7}
                text={String(i)}
                fontSize={14}
              />
            )
          )}

          <Zona />
          <Evento />

        </Layer>
      </Stage>
    </div>
  );
}

export default PlanoCartesiano;