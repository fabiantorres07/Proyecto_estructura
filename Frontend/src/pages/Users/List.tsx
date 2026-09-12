import React, { useState } from "react";
import { User } from "../../models/User";
import GenericTable from "../../components/GenericTable";

const Users: React.FC = () => {
    const [users, setUsers] = useState<User[]>([
        { id: 1, name: "Juan", email: "juan@example.com" },
        { id: 2, name: "Maria", email: "maria@example.com" },
    ]);

    const handleAction = (action: string, item: User) => {
        if (action === "edit") {
            console.log("Edit user:", item);
        } else if (action === "delete") {
            console.log("Delete user:", item);
        }
    };

    return (
        <div>
            <h2>User List</h2>
            <GenericTable
                data={users}
                columns={["id", "name", "email"]}
                actions={[
                    { name: "edit", label: "Edit" },
                    { name: "delete", label: "Delete" },
                ]}
                onAction={handleAction}
            />
        </div>
    );
};

export default Users;
