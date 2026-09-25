import { Group, Rect, Label, Tag, Text } from "react-konva";
import { useState } from "react";
import { Zone as ZoneModel } from "../../models/Zone";

interface MapZoneProps {
  zone?: ZoneModel;
  selected?: boolean;
}

const PLANE_SIZE = 500;
const PLANE_MAX_COORDINATE = 1000;
const PLANE_MARGIN = 45;

function MapZone({ zone, selected = false }: MapZoneProps) {
  const [hover, setHover] = useState(false);

  if (
    zone?.x_min == null ||
    zone.x_max == null ||
    zone.y_min == null ||
    zone.y_max == null
  ) {
    return null;
  }

  const x =
    PLANE_MARGIN + (zone.x_min / PLANE_MAX_COORDINATE) * PLANE_SIZE;
  const y =
    PLANE_MARGIN +
    PLANE_SIZE -
    (zone.y_max / PLANE_MAX_COORDINATE) * PLANE_SIZE;
  const width =
    ((zone.x_max - zone.x_min) / PLANE_MAX_COORDINATE) * PLANE_SIZE;
  const height =
    ((zone.y_max - zone.y_min) / PLANE_MAX_COORDINATE) * PLANE_SIZE;

  return (
    <Group
      onMouseEnter={(e) => {
        setHover(true);
        e.target.getStage()!.container().style.cursor = "pointer";
      }}
      onMouseLeave={(e) => {
        setHover(false);
        e.target.getStage()!.container().style.cursor = "default";
      }}
    >
      <Rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={zone.is_populated ? "#22c55e" : "#3498db"}
        opacity={selected ? 0.9 : 0.65}
        stroke={selected ? "#b45309" : "black"}
        strokeWidth={selected ? 4 : 2}
      />

      {hover && (
        <Label x={x} y={y - 36}>
          <Tag
            fill="black"
            cornerRadius={5}
          />
          <Text
            text={zone.name || "Zona sin nombre"}
            fill="white"
            padding={8}
            fontSize={14}
          />
        </Label>
      )}
    </Group>
  );
}

export default MapZone;