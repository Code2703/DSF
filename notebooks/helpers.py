import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import os
from statsmodels.tsa.seasonal import STL, seasonal_decompose
import seaborn as sns
import math
import datetime
from datetime import datetime


def clean_google(df):
    """Takes a google trends dataframe of weekly resolution as input and returns a pandas dataframe in wide format with weeks as columns, indexed by geography and query pairs."""
    # Replace non-numeric values
    df.replace("<1", 0, inplace=True)
    # Ensure integer input for search activity data
    df[df.columns[1:]] = df[df.columns[1:]].astype(int)
    # Replace any whitespace in column headers with underscores
    df.rename(columns=lambda x: x.replace(' ', '_'), inplace=True)

    # Transpose dataframe
    df.set_index('Woche', inplace=True)
    df = df.T.reset_index()
    
    # Extract canton and query and store in separate columns
    df['canton'] = df['index'].apply(lambda x: x.split("_(")[1].strip("()"))
    df['query'] = df['index'].apply(lambda x: x.split("_(")[0].strip(":"))

    # Re-order columns
    df = df[['canton', 'query', *df.columns[:-2]]].drop(columns='index').set_index(['canton', 'query'])

    return df

def stitch_series(canton, df1, df2):
    """Takes in canton and two google search trend datasets with same queries and different but overlapping timeframes and returns a merged series that is scaled uniformly"""
    # Get list of overlapping columns
    unique_columns = df1.columns.difference(df2.columns)
    duplicate_columns = list(filter(lambda x: x not in unique_columns, df1.columns))

    # Merge non-overlapping columns
    merged_df = df1[duplicate_columns].T.join(df2[duplicate_columns].T, on='Woche', lsuffix='_1', rsuffix='_2')

    # Factors to calculate
    factor_df = pd.DataFrame()
    factor_cols = set(map(lambda x: x[1], merged_df.columns))
    for col in factor_cols:
        factor_df[col+'_fact'] = merged_df[canton+'_1', col] / merged_df[canton+'_2', col]
    # Replace division by zero with NaN before calculating the rescaling factor
    factor_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    # Calculate factor for adjustment of time series across overlapping timesteps and queries (in order to normalize according to same factor)
    factor = factor_df.mean(axis=1, skipna=True).mean(skipna=True)

    # Multiply all values in 2017 dataframe with factor
    scaled_df2 = factor * df2

    # Merge dataframes on indexes
    stitched_df = pd.merge(df1[unique_columns], scaled_df2, left_index=True, right_index=True, how='outer')
    
    stitched_df.replace(np.nan, 0, inplace=True)

    stitched_df = stitched_df.T
    
    for col in stitched_df.columns.levels[1]:
        max_val = stitched_df[canton, col].max()
        stitched_df[canton, col] = (stitched_df[canton, col] / max_val) * 100

    stitched_df.replace(np.nan, 0, inplace=True)

    stitched_df = stitched_df.T
    return stitched_df

    
# Adapted from: https://towardsdatascience.com/comprehensive-time-series-exploratory-analysis-78bf40d16083
def plot_missing(data,
                 start=None,
                 end=None,
                 plot_title=None,
                 annotate_missing=True,
                 font_size=12,
                 figsize=(12, 12)):
    
    x_tick = 16
    
    # Interval to plot
    if start is None:
        start = min(data.index)
    else:
        start = max(start, min(data.index))

    if end is None:
        end = max(data.index)
    else:
        end = min(end, max(data.index))

    # Title and subtitle
    if plot_title is None:
        plot_title = f"Missing Values Heatmap"
    plot_sup_title = (
        f"From {start:%H %p}, {start:%d-%b-%Y} to {end:%H %p}, {end:%d-%b-%Y}"
    )

    # Tick Labels
    # if annotate_missing:
    #     ytick_labels=[canton +\
    #         f"\nMissing:\
    #             {round(data[canton].isna().sum()/data[canton].count()*100, 2)}%"\
    #                  for canton in data.columns]
    # else:
    ytick_labels=[canton for canton in data.columns]

    fig, ax = plt.subplots()
    # Plot heatmap
    sns.heatmap(data.isnull().T, cbar=False)
    ax.figure.set_size_inches(figsize)

    # Set major locator after the plot is rendered
    ax.xaxis.set_major_locator(ticker.LinearLocator(x_tick))

    ax.set_xticklabels(
        [
            timestamp.strftime("%d %b, %Y")
            for timestamp in pd.date_range(
                start=start,
                end=end,
                periods=len(ax.get_xticks()),
            ).to_list()
        ],
        fontsize=font_size - 2,
    )
    ax.yaxis.set_major_locator(ticker.FixedLocator(range(len(ytick_labels))))
    ax.set_yticklabels(ytick_labels, fontsize=font_size - 4)        
    ax.set_xlabel("Date", fontsize=font_size - 1, fontweight="bold")
    ax.set_ylabel("Canton_Query", fontsize=font_size - 1, fontweight="bold")
    ax.set_title(plot_title, y=1.08, fontsize=font_size, fontweight="bold")
    plt.suptitle(plot_sup_title, y=0.94, fontsize=font_size - 1)
    fig.autofmt_xdate()
    plt.show()


def plot_google(df):
    # Define subplot size
    subplot_width = 3
    subplot_height = 2

    # Determine the number of rows and columns for subplots
    num_columns = len(df.columns)
    num_rows = int(math.ceil(num_columns / 4))  # Adjust the divisor to change the number of columns per row
    num_cols = min(num_columns, 4)

    # Calculate total figure size
    fig_width = num_cols * subplot_width
    fig_height = num_rows * subplot_height

    fig, ax = plt.subplots(num_rows, num_cols, figsize=(fig_width, fig_height), sharex=True, sharey=True)

    plt.style.use('ggplot')

    # Adjust the subplots' layout
    fig.subplots_adjust(hspace=0.5, wspace=0.5)

    # Set a common y-axis limit
    y_limit = 110

    # Handle the case of a single row
    if num_rows == 1:
        ax = [ax]

    # Iterate through each subplot and plot the data
    i, j = 0, 0
    for entry in df.columns:
        title = entry.replace("()", "")
        ax[i][j].plot(df[entry], label=entry)
        ax[i][j].set_title(title, fontsize=9)
        ax[i][j].tick_params(axis='x', labelrotation=45)  # Rotate x-axis labels
        ax[i][j].tick_params(axis='both', labelsize=8)  # Set tick label size
        ax[i][j].set_ylim([0, y_limit])  # Set y-axis limit for each subplot

        # Move to next subplot
        j += 1
        if j == num_cols:
            i += 1
            j = 0

    # Hide unused subplots
    for p in range(i, num_rows):
        for q in range(j, num_cols):
            ax[p][q].axis('off')

    # Add overarching title
    plt.suptitle(f'Indexed Cantonal Search Activity for {entry.split("_(")[0].strip(":")}')

    # Adjust overall layout
    plt.tight_layout()

    plt.show()

def plot_stl_decomposition(data, period=None, robust=True, figsize=(10, 8)):
    # Apply STL decomposition
    decomp = STL(data, period=period, robust=robust).fit()  # 'period=52' for weekly data

    # Plot the results
    fig, axs = plt.subplots(4, sharex=True, figsize=figsize)  # Increase the number of subplots to 4

    # Determine the common y-axis range for the components (excluding the original time series for clarity)
    common_ylim = (min(decomp.trend.min(), decomp.seasonal.min(), decomp.resid.min()),
                max(decomp.trend.max(), decomp.seasonal.max(), decomp.resid.max()))

    # Plot the original time series
    axs[0].plot(data, label='Original')
    axs[0].set_title('Original Time Series')
    # Set the y-axis limit for the original time series to its own min and max
    axs[0].set_ylim(data.min(), data.max())

    # Plot each decomposed component with the same y-axis limits
    axs[1].plot(decomp.trend)
    axs[1].set_title('Trend')
    axs[1].set_ylim(common_ylim)

    axs[2].plot(decomp.seasonal)
    axs[2].set_title('Seasonal')
    axs[2].set_ylim(common_ylim)

    axs[3].plot(decomp.resid)
    axs[3].set_title('Residual')
    axs[3].set_ylim(common_ylim)

    # Add region_query pair as supertitle
    plt.suptitle(f'STL decomposition for {data.name}')

    # Show the plot with a tight layout
    plt.tight_layout()
    plt.show()
    return decomp

# Based on ritvik math
def plot_estimated(data, decomposition, figsize=(10, 4)):    
    estimated = decomposition.trend + decomposition.seasonal
    plt.figure(figsize=figsize)
    for year in range(2013, 2024):
        plt.axvline(datetime(year, 1, 1), color='k', linestyle='--', alpha=0.25)
    plt.plot(data, label='Data')
    plt.plot(estimated, label='Estimation')
    plt.legend()
    plt.suptitle(f'Estimation vs. True Data-Series for {data.name}')
    plt.tight_layout()
    plt.show()

# Based on ritvik math
def plot_anomalies(data, decomposition):
    resid_mean = decomposition.resid.mean()
    resid_dev = decomposition.resid.std()
    lower = resid_mean - 3*resid_dev
    upper = resid_mean + 3*resid_dev
    plt.figure(figsize=(10, 4))
    for year in range(2013, 2024):
        plt.axvline(datetime(year, 1, 1), color='k', linestyle='--', alpha=0.15)
    plt.plot(decomposition.resid)
    plt.fill_between([datetime(2013,1,1), datetime(2023,11,18)], lower, upper, color='g', alpha=0.25, linestyle='--')
    plt.suptitle(f'Anomaly Detection in Residuals for {data.name}')
    plt.tight_layout()
    plt.show()