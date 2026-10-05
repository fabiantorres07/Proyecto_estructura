import { EventAssociationItem } from "./EventAssociationItem";

export interface EventAssociationsResponse {
    reference: EventAssociationItem | null;
    candidates: EventAssociationItem[];
    used_as_reference_by: EventAssociationItem[];
}