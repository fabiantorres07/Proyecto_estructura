import { useState } from "react";
import { Group, Label, RegularPolygon, Tag, Text } from "react-konva";
import { Station } from "../../models/Station";

interface MapStationProps {
	station: Station;
	x: number;
	y: number;
	selected?: boolean;
}

function MapStation({ station, x, y, selected = false }: MapStationProps) {
	const [hovered, setHovered] = useState(false);

	return (
		<Group
			onMouseEnter={(event) => {
				setHovered(true);
				event.target.getStage()!.container().style.cursor = "pointer";
			}}
			onMouseLeave={(event) => {
				setHovered(false);
				event.target.getStage()!.container().style.cursor = "default";
			}}
		>
			<RegularPolygon
				x={x}
				y={y}
				sides={3}
				radius={9}
				fill={selected ? "#f59e0b" : "#1018b9"}
				stroke={selected ? "#b45309" : "#060d5f"}
				strokeWidth={2}
			/>
			{hovered && (
				<Label x={x + 10} y={y - 28}>
					<Tag fill="black" cornerRadius={5} />
					<Text
						text={station.station_id || "Estación"}
						fill="white"
						padding={8}
						fontSize={14}
					/>
				</Label>
			)}
		</Group>
	);
}

export default MapStation;
