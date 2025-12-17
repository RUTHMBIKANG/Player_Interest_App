import streamlit as st
import matplotlib.pyplot as plt
from mplsoccer import Pitch

plt.style.use("default")

st.title("Pitch Test")

pitch = Pitch(
    pitch_color='white',
    line_color='black',
    stripe=False
)

fig, ax = pitch.draw(figsize=(8, 5))
fig.patch.set_facecolor('white')
ax.set_facecolor('white')

st.pyplot(fig, clear_figure=True)
plt.close(fig)
