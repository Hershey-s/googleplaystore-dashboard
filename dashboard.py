# combined_dashboard.py

import pandas as pd
import plotly.express as px
from datetime import datetime
import pytz
from dash import Dash, html, dcc

# ---------- Load Data ----------
df_apps = pd.read_csv("Play Store Data.csv")

# --------- Common Time Settings ----------
ist = pytz.timezone("Asia/Kolkata")
now = datetime.now(ist)

# ---------- Prepare Data for Choropleth Map ----------
def prepare_choropleth_data():
    import pycountry
    import random

    df = df_apps.copy()

    df = df[df['Installs'].str.contains('[0-9]', na=False)]
    df['Installs'] = df['Installs'].str.replace('[+,]', '', regex=True)

    def clean_installs(x):
        if str(x).strip().lower() == 'free':
            return None
        try:
            return float(x)
        except:
            return None

    df['Installs'] = df['Installs'].apply(clean_installs)
    df = df.dropna(subset=['Installs'])

    # Remove unwanted categories
    df = df[~df['Category'].str.startswith(('A', 'C', 'G', 'S'))]

    top_categories = df.groupby('Category')['Installs'].sum()
    top5 = top_categories[top_categories > 1_000_000].sort_values(ascending=False).head(5).index.tolist()

    df = df[df['Category'].isin(top5)].copy()

    countries = [country.name for country in pycountry.countries]
    df['Country'] = random.choices(countries, k=len(df))

    def get_iso3(country_name):
        try:
            return pycountry.countries.lookup(country_name).alpha_3
        except:
            return None

    df['iso_alpha'] = df['Country'].apply(get_iso3)
    df = df.dropna(subset=['iso_alpha'])

    return df

def get_choropleth(df_top5):
    fig = px.choropleth(
        df_top5,
        locations='iso_alpha',
        color='Installs',
        hover_name='App',
        animation_frame='Category',
        title='Global Installs by App Category (6–8 PM IST)',
        color_continuous_scale='Blues',
    )
    fig.update_layout(geo=dict(showframe=False, showcoastlines=True))
    return fig

# ---------- Prepare Data for Time Series ----------
def prepare_time_series_data():
    df = df_apps.copy()

    df = df[df['Installs'].str.contains('[0-9]', na=False)]
    df['Installs'] = df['Installs'].str.replace('[+,]', '', regex=True)

    def clean_installs(x):
        if str(x).strip().lower() == 'free':
            return None
        try:
            return float(x)
        except:
            return None

    df['Installs'] = df['Installs'].apply(clean_installs)
    df = df.dropna(subset=['Installs'])

    df['Reviews'] = pd.to_numeric(df['Reviews'], errors='coerce')
    df = df.dropna(subset=['Reviews'])
    df = df[df['Reviews'] > 500]

    df = df[df['Category'].str.startswith(('E', 'C', 'B'))]

    df = df[
        ~df['App'].str.lower().str.startswith(('x', 'y', 'z')) &
        ~df['App'].str.contains('S', case=False)
    ]

    translations = {
        'Beauty': 'सुंदरता',
        'Business': 'வர்த்தகம்',
        'Dating': 'Dating'  # You can change to 'Verabredung' if preferred
    }
    df['Translated_Category'] = df['Category'].map(translations).fillna(df['Category'])

    df['Last Updated'] = pd.to_datetime(df['Last Updated'], errors='coerce')
    df = df.dropna(subset=['Last Updated'])
    df['Month'] = df['Last Updated'].dt.to_period('M').dt.to_timestamp()

    df_grouped = (
        df.groupby(['Month', 'Translated_Category'])['Installs']
        .sum()
        .reset_index()
    )

    df_grouped['MoM_Growth'] = df_grouped.groupby('Translated_Category')['Installs'].pct_change()
    df_grouped['Significant_Growth'] = df_grouped['MoM_Growth'] > 0.20

    return df_grouped

def plot_time_series(df_grouped):
    fig = px.line(
        df_grouped,
        x='Month',
        y='Installs',
        color='Translated_Category',
        title='Total Installs Over Time by Category (6–9 PM IST)'
    )

    for category in df_grouped['Translated_Category'].unique():
        cat_data = df_grouped[df_grouped['Translated_Category'] == category]
        growth_data = cat_data[cat_data['Significant_Growth']]

        fig.add_traces(px.area(
            growth_data,
            x='Month',
            y='Installs'
        ).update_traces(opacity=0.3, name=f'{category} Growth > 20%').data)

    fig.update_layout(xaxis_title='Month', yaxis_title='Total Installs', legend_title='Category')
    return fig

# ---------- Build Dash App ----------
app = Dash(__name__)
app.title = "Play Store Combined Dashboard"

# Prepare data upfront
choropleth_data = prepare_choropleth_data()
time_series_data = prepare_time_series_data()

# Check visibility windows
show_map = 18 <= now.hour < 20
show_chart = 18 <= now.hour < 21

app.layout = html.Div([
    html.H1("📱 Play Store Combined Dashboard", style={"textAlign": "center"}),

    dcc.Tabs([
        dcc.Tab(label='Global Choropleth Map', children=[
            dcc.Graph(
                id='choropleth-map',
                figure=get_choropleth(choropleth_data) if show_map else {}
            ),
            html.P(
                "Map is only visible between 6 PM and 8 PM IST.",
                style={"color": "red", "fontWeight": "bold"} if not show_map else {"display": "none"}
            )
        ]),
        dcc.Tab(label='Time Series Chart', children=[
            dcc.Graph(
                id='time-series-chart',
                figure=plot_time_series(time_series_data) if show_chart else {}
            ),
            html.P(
                "Chart is only visible between 6 PM and 9 PM IST.",
                style={"color": "red", "fontWeight": "bold"} if not show_chart else {"display": "none"}
            )
        ])
    ])
])

if __name__ == "__main__":
    app.run(debug=True)
