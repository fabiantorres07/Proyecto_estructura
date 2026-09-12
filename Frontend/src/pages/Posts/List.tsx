import React, { useEffect, useState } from "react";
import { Post } from "../../models/Post";
import GenericTable from "../../components/GenericTable";
import { postService } from "../../services/postService";
import Swal from "sweetalert2";
import { useNavigate } from "react-router-dom";

const Posts: React.FC = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<Post[]>([]);

    useEffect(() => {
        fetchData();
    }, []);

    const fetchData = async () => {
        const posts = await postService.getPosts();
        setData(posts);
    };

    const handleAction = (action: string, item: Post) => {
        if (action === "edit") {
            console.log("Edit post:", item);
            navigate(`/posts/update/${item.id}`);
        } else if (action === "delete") {
            console.log("Delete post:", item);
            deletePost(item.id ? item.id : 0);
        }
    };

    const deletePost = async (id: number) => {
        Swal.fire({
            title: "¿Estás seguro que quiere eliminar?",
            text: "¡No podrás revertir esto!",
            icon: "warning",
            showCancelButton: true,
            confirmButtonColor: "#3085d6",
            cancelButtonColor: "#d33",
        }).then(async (result) => {
            if (result.isConfirmed) {
                const success = await postService.deletePost(id);
                if (success) {
                    Swal.fire(
                        "¡Eliminado!",
                        "El post ha sido eliminado.",
                        "success"
                    );
                    fetchData();
                } else {
                    console.error("Error al eliminar el post con id:", id);
                    Swal.fire({
                        icon: "error",
                        title: "Error",
                        text: "No se pudo eliminar el post. Por favor, inténtalo de nuevo.",
                    });
                }
            }
        });
    };

    const handleCreate = () => {
        console.log("Create post");
        navigate("/posts/create");
    };

    return (
        <div>
            <h2>Post List</h2>
            <button
                onClick={handleCreate}
                className="inline-flex items-center justify-center bg-primary py-2 px-4 text-sm font-medium text-white rounded-md hover:bg-opacity-90 transition"
            >
                Crear
            </button>

            <GenericTable
                data={data}
                columns={["id", "title", "body"]}
                actions={[
                    { name: "edit", label: "Edit" },
                    { name: "delete", label: "Delete" },
                ]}
                onAction={handleAction}
            />
        </div>
    );
};

export default Posts;



