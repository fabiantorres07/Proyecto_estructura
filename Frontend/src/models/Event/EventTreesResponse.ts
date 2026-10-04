import { EventTreeNode } from "./EventTreeNode";

export interface EventTreesResponse {
    avl: EventTreeNode | null;
    bst: EventTreeNode | null;
}