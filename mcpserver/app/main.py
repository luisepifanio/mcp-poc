import random

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel

app = FastAPI(title="Simple API")


class Hello(BaseModel):
    message: str


# health check endpoint
@app.get("/ping")
async def ping() -> str:
    return "pong"


@app.get("/hello", operation_id="say_hello")
async def hello(name: str | None = None) -> Hello:
    """A simple greeting endpoint, used for greeting on 'Please Greet {name}' and testing MCP local functionality."""
    return Hello(message=f"Hello {name} KUN!" if name else "Hello stranger KUN!")


@app.get("/add/{a}/{b}", operation_id="add_integers")
def add(a: int, b: int) -> int:
    """Adds two integer numbers tog ether."""
    return a + b


@app.get("/cordoba_jokes", operation_id="get_cordoba_jokes")
async def get_cordoba_jokes() -> str:
    """Get cordoba jokes"""
    # List of cordoba jokes
    jokes = [
        "Un cordobés arriba de una higuera, pasa uno y le pregunta: 'Che, ¿qué hacé' ahí arriba?' Y el de arriba contesta: 'Comiendo mandarinas'. 'Pero si eso e' una higuera!', le dice el de abajo. 'Y a mí qué me importa, si las mandarinas las traigo en el bolsiio!'",
        "Un porteño le dice a un cordobés de visita: '¿Qué te parese si vamos a comer al Tigre, cordobé?' El cordobés responde: '¿Y no é' má' fácil agarrá' un pollo, tío?'",
        "Estaba un tipo con dos dedos metidos en un enchufe largando chispas. Llega la esposa y le pregunta: '¡Pichi, te estái electrocutando?' Él contesta: '¡No, si me voy a haber disfrazado de arbolito e' Navidá!'",
        "Dos borrachos cordobeses: 'Che, loco, ya hace como dos días que no tomo.' '¿Cómo?' 'Sí, mañana y pasao.'",
        "Un mozo le pregunta a un cordobés en un restaurante: '¿La tortilla la prefiere a la portuguesa o a la española?' El cordobés contesta: 'E' igual, varón, yo la quiero pa' comela, no pa' charlá'.",
        "Un cordobés a un mozo: 'Mozo, hay una mosca en mi sopa.' El mozo: '¿Se la saco?' El cordobés: 'No, macho, ponele cubierto.'",
        "Una señora a un cordobés: '¡Señor, le vendo un reloj!' Él: '¿Qué marca?' La señora: 'La hora, negro, ¿qué querí' que marque?'",
        "La mujer prueba el whisky del marido y hace un gesto de asco: '¡No sé cómo te puede gustar esta porquería!' El marido: '¿Ahora te das cuenta el sacrificio que tengo que hacer para chuparme?'",
        "Un cordobés entra a una farmacia: 'Che, ¿tené' pastillas anticonceptivas?' El farmacéutico: 'Sí, señor. ¿Para su esposa?' El cordobés: 'No, varón, pa' mí, ¡pa' poder dormir tranquilo!'",
        "La maestra en clase: 'A ver, Martita, ¿usted qué quiere ser cuando sea grande?' 'Yo quiero ser mamá, señorita.' '¿Y usted, Juancito?' 'Yo quiero ayuda' a la Martita a ser mamá, señorita.'",
        "Un cordobés ve a otro con el brazo enyesado. Le pregunta: 'Che, ¿qué te pasó, hermano?' El otro: 'No, ¿sabé' lo que pasa? El finde pasado fui a un velorio y había una mina tan buena que le entré como rengo a la muleta.'",
        "Un cordobés: 'No sabé' loco, mi barrio tiene tanta inseguridad que el otro día un tipo soñó que ganaba la lotería ¡y lo despertó a los gritos pa' robarle la plata!'",
        "Un cordobés le dice a otro: 'La mina e' tan, pero tan, pero tan flaca, que le picó una avispa en el pecho y la roncha le salió en la espalda.'",
        "Un borracho llega a la casa, la mujer le tira la llave por la ventana. '¡Tomá, borracho de mierda!' El tipo mira la llave en el pasto y le dice: 'No, tirame la soga, que si agarro la llave, la vuelvo a perder.'",
        "Dice un cordobés: 'Le doy le doy le doy hasta que Pinocho done sangre.'",
        "La abuela cordobesa ve a su nieto volviendo del colegio con el cuaderno rojo. '¿Y ésto, m'hijo? ¿Qué pasó?' El nieto: 'Problemas, abu...' La abuela: '¡Ay, Dios! ¡Si tuvierai problema' con el culo en vez del cuaderno, te lo arreglaba yo de un escobazo!'",
        "Un cordobés dice: 'Tengo un auto que calienta tanto, loco, que calienta hasta cuando lo lavo.'",
        "Una mujer le dice al doctor: 'Doctor, no sé si prefiero sacarme esta muela o tener un hijo.' El dentista le responde: 'Bueno, señora. Decídase de una vez, ¡así sé en qué posición pongo el sillón!'",
        "Un cordobés le dice a su amigo: '¡Qué mujer más contradictoria mi vieja! Me pide que le haga el amor arriba de la mesa, pero si me como un sandwichito en la cama, ¡me saca cagando!'",
        "Un cordobés está en la calle gritando: '¡VENDO PRESTOBARBA, VENDO PRESTOBARBA!' Pasa un guaso y le dice: 'Che, guaso, ¿la vendei' o la prestai'?'",
    ]

    return random.choice(jokes)


# Expose MCP server
mcp = FastApiMCP(
    app,
    name="Simple API MCP",
    # base_url="http://localhost:8000",
    include_operations=["get_cordoba_jokes", "add_integers", "say_hello"],
    describe_all_responses=True,  # Include all possible response schemas in tool descriptions
    describe_full_response_schema=True,  # Include full JSON schema in tool descriptions
)
 
mcp.mount()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
