import { useEffect, useRef, useState } from "react";
import { Stage, Layer, Line, Text, Circle, Group, Label, Tag } from "react-konva";
import MapZone from "./MapZone";
import MapStation from "./MapStation";
import { Station } from "../../models/Station";
import { EventMapPoint } from "../../models/Event/EventMapPoint";
import { Zone } from "../../models/Zone";

const GRID_SIZE = 10;
const CELL_SIZE = 50;
const GRID_STEP_KM = 100;
const MARGIN = 45;
const MIN_SCALE = 0.5;
const MAX_SCALE = 3;
const ZOOM_STEP = 1.2;

interface CartesianPlaneProps {
  zones?: Zone[];
  selectedZone?: Zone | null;
  stations?: Station[];
  selectedStation?: Station | null;
  events?: EventMapPoint[];
  highlightedEventId?: number | null;
  highlightedStationIds?: string[];
}

function CartesianPlane({
  zones = [],
  selectedZone = null,
  stations = [],
  selectedStation = null,
  events = [],
  highlightedEventId = null,
  highlightedStationIds = [],
}: CartesianPlaneProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hoveredMarker, setHoveredMarker] = useState<string | null>(null);

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
  const mapCoordinate = (coordinate: number) =>
    MARGIN + (coordinate / (GRID_SIZE * GRID_STEP_KM)) * (GRID_SIZE * CELL_SIZE);

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

      {width > 0 && height > 0 && (
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
              x={originX + i * CELL_SIZE - 20}
              y={originY + 14}
              text={String(i * GRID_STEP_KM)}
              fontSize={13}
              width={40}
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

          {zones.map((zone, index) => (
            <MapZone
              key={zone.name || `${zone.x_min}-${zone.y_min}-${index}`}
              zone={zone}
              selected={
                selectedZone === zone ||
                (selectedZone?.name != null && selectedZone.name === zone.name)
              }
            />
          ))}

          {stations.map((station, index) => {
            if (station.x == null || station.y == null) {
              return null;
            }

            const x = mapCoordinate(station.x);
            const y = originY - (station.y / (GRID_SIZE * GRID_STEP_KM)) * (GRID_SIZE * CELL_SIZE);

            return (
              <MapStation
                key={`station-${station.station_id ?? index}`}
                station={station}
                x={x}
                y={y}
                selected={
                  selectedStation === station ||
                  (selectedStation?.station_id != null &&
                    selectedStation.station_id === station.station_id) ||
                  (station.station_id != null && highlightedStationIds.includes(station.station_id))
                }
              />
            );
          })}

          {events.map((mapEvent, index) => {
            const markerKey = `event-${mapEvent.event_id}`;
            const x = mapCoordinate(mapEvent.x);
            const y = originY - (mapEvent.y / (GRID_SIZE * GRID_STEP_KM)) * (GRID_SIZE * CELL_SIZE);
            const highlighted = highlightedEventId === mapEvent.event_id;

            return (
              <Group
                key={`${markerKey}-${index}`}
                onMouseEnter={(event) => {
                  setHoveredMarker(markerKey);
                  event.target.getStage()!.container().style.cursor = "pointer";
                }}
                onMouseLeave={(event) => {
                  setHoveredMarker(null);
                  event.target.getStage()!.container().style.cursor = "default";
                }}
              >
                <Circle
                  x={x}
                  y={y}
                  radius={highlighted ? 12 : 8}
                  fill={highlighted ? "#f59e0b" : "#ef4444"}
                  stroke={highlighted ? "#92400e" : "#991b1b"}
                  strokeWidth={highlighted ? 3 : 2}
                />
                {hoveredMarker === markerKey && (
                  <Label x={x + 10} y={y - 28}>
                    <Tag fill="black" cornerRadius={5} />
                    <Text
                      text={String(mapEvent.event_id)}
                      fill="white"
                      padding={8}
                      fontSize={14}
                    />
                  </Label>
                )}
              </Group>
            );
          })}
        </Layer>
        </Stage>
      )}
    </div>
  );
}

export default CartesianPlane;