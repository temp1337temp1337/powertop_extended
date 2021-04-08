import pandas
import plotly
import json
import powertop

COLOR_LIST = ["#0099C6",
              "#FFA15A",
              "rgb(204,204,204)",
              "rgb(179,222,105)"]
WIDTH = 1400
HEIGHT = 800


def update_df(process, data):
    columns = ["usage", "pw_estimate"]
    dataframe = pandas.DataFrame(columns=columns)
    i = 0
    j = 0

    for measure in data:
        measure_data = json.loads(measure)[0]
        dataframe.loc[i] = [0, 0]
        for entry in measure_data:
            if process in entry["Description"] and "sh -c" not in entry["Description"]:
                usage = entry["Usage"].strip().split(' ')[0]
                usage_metric = entry["Usage"].strip().split(' ')[1]
                if usage_metric == "us/s":
                    usage = float(usage) * 0.001

                pw_estimate = entry["PW Estimate"].strip().split(' ')[0]
                pw_estimate_metric = entry["PW Estimate"].strip().split(' ')[1]
                if pw_estimate_metric == "mW":
                    pw_estimate = float(pw_estimate) * 0.001
                if pw_estimate_metric == "uW":
                    pw_estimate = float(pw_estimate) * 0.000001

                dataframe.iat[i, 0] += float(usage)
                dataframe.iat[i, 1] += float(pw_estimate)
                j += 1

        if j != 0:
            dataframe.iat[i, 0] = dataframe.iat[i, 0]/j
            dataframe.iat[i, 1] = dataframe.iat[i, 1]/j

        j = 0
        i += 1

    return dataframe


def draw_graph(dataframe, dataframe_other, graph, element):
    min_dt = min(dataframe.index.values)
    max_dt = max(dataframe.index.values)
    data = []
    if graph == 'line':
        data = [
            plotly.graph_objects.Scatter(
                x=dataframe.index.values,
                y=dataframe[element],
                name='ARM (4 cores)',
                mode='markers+lines',
                line=dict(color=COLOR_LIST[0])
            ),
            plotly.graph_objects.Scatter(
                x=dataframe.index.values,
                y=dataframe_other[element],
                name='x86_64 (24 cores)',
                mode='markers+lines',
                line=dict(color=COLOR_LIST[1])
            )
        ]
    text, title_text = "", ""
    if element == "pw_estimate":
        text = 'Power estimation in mW (milliWatts) per time unit'
        title_text = 'Estimation in mW'
    if element == "usage":
        text = 'Number of runs per time unit'
        title_text = 'Estimation in ms/s (milliseconds/second)'
    if element == "tradeoff":
        text = 'Tradeoff (Performance/Power)'
        title_text = 'Estimation in mW/(ms/s) [milliWatts/(milliseconds/second)]'

    layout = plotly.graph_objects.Layout(
        yaxis=dict(showgrid=True, gridcolor='rgba(217,217,217, 0.5)'),
        title=dict(text=text, x=0.5),
        legend=dict(orientation='h',
                    yanchor='bottom',
                    y=-0.1,
                    xanchor='center',
                    x=0.5),
        plot_bgcolor='white',
        xaxis=dict(showgrid=True, gridcolor='rgba(217,217,217, 0.5)',
                   range=[min_dt, max_dt]),
    )
    fig = plotly.graph_objects.Figure(data=data, layout=layout)
    fig.update_xaxes(title_text=''.join([
        'Time Units (per 10 minutes)']))
    fig.update_yaxes(title_text=title_text)
    fig.write_image(''.join(['measurements_', element, '.jpg']),
                    width=WIDTH, height=HEIGHT)
    return 


if __name__ == "__main__":
    time = 60

    measures = powertop.Powertop().get_measures(
        time=time, iterations=3, 
        section="Overview of Software Power Consumers",
        filename="report")
    process = "libressl"
    measures_dataframe = update_df(process=process, data=measures)
    measures_dataframe.to_csv("measures_dataframe_x86_64.csv", mode='w+', header=True)
    df_arm = pandas.read_csv("measures_dataframe_arm.csv", header=0)
    df_x86_64 = pandas.read_csv("measures_dataframe_x86_64.csv", header=0)
    draw_graph(dataframe=df_arm, dataframe_other=df_x86_64, 
               graph="line", graph_time=time, element="usage")
    draw_graph(dataframe=df_arm, dataframe_other=df_x86_64, 
               graph="line", graph_time=time, element="pw_estimate")
    draw_graph(dataframe=df_arm, dataframe_other=df_x86_64, 
               graph="line", graph_time=time, element="tradeoff")

