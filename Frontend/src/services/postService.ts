import { api } from "../interceptors/authInterceptor"; // ajusta la ruta
import { Post } from "../models/Post";

const API_URL = "/posts"; // ya no necesitas baseURL aquí

class PostService {
    async getPosts(): Promise<Post[]> {
        try {
            const response = await api.get<Post[]>(API_URL);
            return response.data;
        } catch (error) {
            console.error("Error al obtener posts:", error);
            return [];
        }
    }

    async getPostById(id: number): Promise<Post | null> {
        try {
            const response = await api.get<Post>(`${API_URL}/${id}`);
            return response.data;
        } catch (error) {
            console.error("Post no encontrado:", error);
            return null;
        }
    }

    async createPost(post: Omit<Post, "id">): Promise<Post | null> {
        try {
            const response = await api.post<Post>(API_URL, post);
            return response.data;
        } catch (error) {
            console.error("Error al crear post:", error);
            return null;
        }
    }

    async updatePost(id: number, post: Partial<Post>): Promise<Post | null> {
        try {
            const response = await api.put<Post>(`${API_URL}/${id}`, post);
            return response.data;
        } catch (error) {
            console.error("Error al actualizar post:", error);
            return null;
        }
    }

    async deletePost(id: number): Promise<boolean> {
        try {
            await api.delete(`${API_URL}/${id}`);
            return true;
        } catch (error) {
            console.error("Error al eliminar post:", error);
            return false;
        }
    }
}

// Instancia reutilizable
export const postService = new PostService();