import { useEffect, useRef, useState } from "react";
import { Stage, Layer, Line, Text } from "react-konva";
import Zone from "./Zone";
import Event from "./Event";

const GRID_SIZE = 10;
const CELL_SIZE = 50;
const GRID_STEP_KM = 100;
const MARGIN = 45;
const MIN_SCALE = 0.5;
const MAX_SCALE = 3;
const ZOOM_STEP = 1.2;

function CartesianPlane() {
  const containerRef = useRef<HTMLDivElement>(null);

  const [size, setSize] = useState({
    width: 0,
    height: 0,
  });
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;

      setSize({
        width,
        height,
      });
    });

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  const { width, height } = size;
  const canvasWidth = GRID_SIZE * CELL_SIZE + MARGIN * 2;
  const canvasHeight = GRID_SIZE * CELL_SIZE + MARGIN * 2;
  const originX = MARGIN;
  const originY = MARGIN + GRID_SIZE * CELL_SIZE;

  const zoom = (factor: number) => {
    setScale((currentScale) =>
      Math.min(MAX_SCALE, Math.max(MIN_SCALE, currentScale * factor))
    );
  };

  const resetView = () => {
    setScale(1);
    setPosition({
      x: Math.max(0, (width - canvasWidth) / 2),
      y: Math.max(0, (height - canvasHeight) / 2),
    });
  };

  useEffect(() => {
    resetView();
  }, [width, height]);

  const handleWheel = (event: any) => {
    event.evt.preventDefault();
    zoom(event.evt.deltaY > 0 ? 1 / ZOOM_STEP : ZOOM_STEP);
  };

  return (
    <div ref={containerRef} className="relative h-full w-full overflow-hidden rounded-md border border-stroke bg-white">
      <div className="absolute right-3 top-3 z-10 flex gap-2">
        <button type="button" onClick={() => zoom(ZOOM_STEP)} className="h-8 w-8 rounded bg-white text-lg shadow" aria-label="Acercar">
          +
        </button>
        <button type="button" onClick={() => zoom(1 / ZOOM_STEP)} className="h-8 w-8 rounded bg-white text-lg shadow" aria-label="Alejar">
          -
        </button>
        <button type="button" onClick={resetView} className="rounded bg-white px-3 text-sm shadow">
          Restablecer
        </button>
      </div>

      <Stage
        width={width}
        height={height}
        x={position.x}
        y={position.y}
        scaleX={scale}
        scaleY={scale}
        draggable
        onDragEnd={(event) => setPosition(event.target.position())}
        onWheel={handleWheel}
      >
        <Layer>
          {Array.from({ length: GRID_SIZE + 1 }, (_, i) => {
            const x = originX + i * CELL_SIZE;

            return (
              <Line key={`grid-${i}`} points={[x, MARGIN, x, originY]} stroke="#dbe3ef" strokeWidth={1} />
            );
          })}

          {Array.from({ length: GRID_SIZE + 1 }, (_, i) => {
            const y = originY - i * CELL_SIZE;

            return (
              <Line key={`grid-row-${i}`} points={[originX, y, originX + GRID_SIZE * CELL_SIZE, y]} stroke="#dbe3ef" strokeWidth={1} />
            );
          })}

          <Line points={[originX, originY, originX + GRID_SIZE * CELL_SIZE, originY]} stroke="black" strokeWidth={2} />
          <Line points={[originX, originY, originX, MARGIN]} stroke="black" strokeWidth={2} />

          {Array.from({ length: GRID_SIZE + 1 }, (_, i) => (
            <Text
              key={`x-label-${i}`}
              x={originX + i * CELL_SIZE - 12}
              y={originY + 14}
              text={String(i * GRID_STEP_KM)}
              fontSize={13}
              width={24}
              align="center"
            />
          ))}

          {Array.from({ length: GRID_SIZE + 1 }, (_, i) => (
            <Text
              key={`y-label-${i}`}
              x={originX - 42}
              y={originY - i * CELL_SIZE - 7}
              text={String(i * GRID_STEP_KM)}
              fontSize={13}
              width={32}
              align="right"
            />
          ))}

          <Text
            x={originX + (GRID_SIZE * CELL_SIZE) / 2 - 25}
            y={originY + 36}
            text="X (km)"
            fontSize={13}
            width={50}
            align="center"
          />
          <Text
            x={originX - 62}
            y={MARGIN + (GRID_SIZE * CELL_SIZE) / 2 + 25}
            text="Y (km)"
            fontSize={13}
            rotation={-90}
            width={50}
            align="center"
          />

          <Zone />
          <Event />
        </Layer>
      </Stage>
    </div>
  );
}

export default CartesianPlane;