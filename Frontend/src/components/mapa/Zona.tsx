import { Group, Rect, Label, Tag, Text } from "react-konva";
import { useState } from "react";

function Zona() {
  const [hover, setHover] = useState(false);

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
        x={200}
        y={150}
        width={100}
        height={60}
        fill="#3498db"
        stroke="black"
        strokeWidth={2}
      />

      {hover && (
        <Label x={200} y={120}>
          <Tag
            fill="black"
            cornerRadius={5}
          />
          <Text
            text="Zona 1"
            fill="white"
            padding={8}
            fontSize={14}
          />
        </Label>
      )}
    </Group>
  );
}

export default Zona;