from structures import avl_node

class avl_tree:
    def __init__(self):

        self.root = None #Para consultar altura de todo el arbol se hace self.root.height


    #HEIGHT
    def height(self, node):
        if node is None:
            return 0
        return node.height

    #BALANCE FACTOR
    def bf(self, node):
        if node is None:
            return 0
        return self.height(node.left)-self.height(node.right)

    #para poder eliminar nodo caso 2 hijos
    def minimum(self,node):# el minimo baja a la izquierda del nodo actual y luego a la derecha
        while node.left is not None:
            node= node.left
        return node

    #ROTATION
    #LL
    def rotation_LL(self, desbalanced):
        middle= desbalanced.left
        subtree=middle.right

        middle.right=desbalanced
        desbalanced.left=subtree

        #heights
        middle.height=(1+max(self.height(middle.left), self.height(middle.right)))
        desbalanced.height=(1+max(self.height(desbalanced.left), self.height(desbalanced.right)))
        return middle
    
    #RR
    def rotation_RR(self, desbalanced):
        middle= desbalanced.right
        subtree=middle.left

        middle.left=desbalanced
        desbalanced.right=subtree

        #heights
        middle.height=(1+max(self.height(middle.left), self.height(middle.right)))
        desbalanced.height=(1+max(self.height(desbalanced.left), self.height(desbalanced.right)))

        return middle
    
    #INSERTION
    def insertion(self, value):
        self.root = self._insertion(self.root, value)

    def _insertion(self, node, value): #recursivo auxiliar
        if node is None:
            return avl_node(value) #Llego a None entonces crea un nuevo nodo

        #se mueve al subarbol izquierdo
        if value<node.value: #value el valor que se quiere meter y node.value el nodo que ya esta, como que primero es un valor y luego al insertarse se convierte en nodo
            node.left= self._insertion(node.left, value)

        #se mueve al subarbol derecho
        if value>node.value:
            node.right= self._insertion(node.right,value)
        # Si value == node.value, no se inserta repetido

        # Actualizar altura del nodo actual
        node.height = 1 + max(
            self.height(node.left),
            self.height(node.right)
        )

        bf=self.bf(node) #En todo el codigo node es el nodo desbalanceado
        if bf>1 or bf<-1:
            if bf>1:
                if value<node.left.value:
                    return self.rotation_LL(node) #es rotacion LL
                
                else: #es rotacion LR
                    #se hace giro simple izquierda
                    node.left=self.rotation_RR(node.left)
                    return self.rotation_LL(node)
            if bf<-1:
                if value>node.right.value:
                    return self.rotation_RR(node) #rotation RR
                else:
                    node.right=self.rotation_LL(node.right) #se hace rotacion RL
                    return self.rotation_RR(node)
        else:
            return avl_node
        
#ELIMINATION

    def elimination(self, node, value):
        if node is None:
            return None

        #se mueve al subarbol izquierdo
        if value<node.value:
            node.left= self.elimination(node.left, value)

        #se mueve al subarbol derecho
        if value>node.value:
            node.right = (self.elimination(node.right, value))

        #node found
        if value == node.value:
            #leaf case
            if node.left==None and node.right==None:
                return None

            #one child case
            #if the evaluated node son is none it means the other son will 
            #be in the eliminated node position
            if node.left is None:
                return node.right
            if node.right == None:
                return node.left

            #two child case
            if node.left!= None and node.right != None:{}