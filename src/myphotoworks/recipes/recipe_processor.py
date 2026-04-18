"""apply_recipe — orchestrates the film simulation effect chain."""
from __future__ import annotations

from PIL import Image

from myphotoworks.recipes.recipe_data import FilmSim, RecipeData
from myphotoworks.recipes import recipe_effects


def apply_recipe(image: Image.Image, recipe: RecipeData) -> Image.Image:
    """Apply all recipe steps in canonical Fujifilm order.

    Order: WB → Film Sim → Tone Curve → Saturation → Clarity → Sharpness → Grain

    Steps with neutral/default values are skipped for performance.
    """
    # 1. White balance
    if recipe.wb_kelvin != 5500 or recipe.wb_shift_r != 0 or recipe.wb_shift_b != 0:
        image = recipe_effects.apply_wb(
            image, recipe.wb_kelvin, recipe.wb_shift_r, recipe.wb_shift_b
        )

    # 2. Film simulation
    if recipe.film_sim != FilmSim.NONE:
        image = recipe_effects.apply_film_sim(image, recipe.film_sim.value)

    # 3. Tone curve
    if recipe.tone_shadow != 0 or recipe.tone_highlight != 0:
        image = recipe_effects.apply_tone_curve(
            image, recipe.tone_shadow, recipe.tone_highlight
        )

    # 4. Saturation
    if recipe.color != 0:
        image = recipe_effects.apply_saturation(image, recipe.color)

    # 5. Clarity
    if recipe.clarity != 0:
        image = recipe_effects.apply_clarity(image, recipe.clarity)

    # 6. Sharpness
    if recipe.sharpness != 0:
        image = recipe_effects.apply_sharpness(image, recipe.sharpness)

    # 7. Grain
    if recipe.grain_effect != "off":
        image = recipe_effects.apply_grain(image, recipe.grain_effect)

    return image
