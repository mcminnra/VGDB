import ast

import numpy as np
from sklearn import metrics
from sklearn.model_selection import train_test_split
import xgboost as xgb

from vgdb import get_game_data

def explode_binary(df, explode_col):
    df_tags = df[[explode_col]]
    UNIQUE_TAGS = sorted(list(set([tag for row in df_tags[explode_col].tolist() if row for tag in row])), reverse=False)
    df_tags[[f'{explode_col}_{tag}' for tag in UNIQUE_TAGS]] = 0

    # Map tag postion importance to column
    for row_idx, row in df_tags.iterrows():
        if row[explode_col]:
            for tag in row[explode_col]:
                df_tags.at[row_idx, f'{explode_col}_{tag}'] = 1
    df_tags = df_tags.drop([explode_col], axis=1)
    return df_tags


if __name__ == '__main__':
    df = get_game_data().set_index('igdb_id')
    df = df.drop(['steam_appid', 'ps_np_title_id'], axis=1)

    print(df.columns)
    #==  Data process

    # Fillna
    for col in ['playtime_hours', 'achievement_progress', 'reviews_percent']:
        df[col] = df[col].fillna(0)
    df['description'] = df['description'].fillna("")

    # platforms
    df['platforms'] = df['platforms'].apply(ast.literal_eval)  # Convert 'object' to list
    df['platforms'] = df['platforms'].apply(lambda d: d if isinstance(d, list) else [])  # fillna
    df['platforms'] = df['platforms'].apply(lambda X: list(set([x.lower().replace('/', ' ').replace('(', '').replace(')', '').replace('\'', '').replace(',', '').replace('<', '').replace('>', '').replace(':', '').replace('[', '').replace(']', '') for x in X])))  # process
    df = df.merge(explode_binary(df, 'platforms'), how='inner', right_index=True, left_index=True, suffixes=(None, None)).drop(['platforms'], axis=1).drop_duplicates()

    # tags
    df['tags'] = df['tags'].apply(ast.literal_eval)  # Convert 'object' to list
    df['tags'] = df['tags'].apply(lambda d: d if isinstance(d, list) else [])  # fillna
    df['tags'] = df['tags'].apply(lambda X: list(set([x.lower().replace('/', ' ').replace('(', '').replace(')', '').replace('\'', '').replace(',', '').replace('<', '').replace('>', '').replace(':', '').replace('[', '').replace(']', '') for x in X])))  # process
    df = df.merge(explode_binary(df, 'tags'), how='inner', right_index=True, left_index=True, suffixes=(None, None)).drop(['tags'], axis=1).drop_duplicates()

    #== Train/Test split
    # TODO Drop these columns for now until we can properly process them
    titles = df['title']
    df = df.drop(['title', 'last_played', 'description'], axis=1)

    train = df[df['personal_rating'].notnull()]  # NOTE: Might weight examples by playtime in the future
    test = df[df['personal_rating'].isnull()].drop(['personal_rating'], axis=1)
    y_train = train['personal_rating']
    X_train = train.drop(['personal_rating'], axis=1)

    X_train, X_val, y_train, y_val = train_test_split(X_train, y_train, train_size=0.8)
    print(f'X train: {X_train.shape}')
    print(f'y train: {y_train.shape}')
    print(f'X val: {X_val.shape}')
    print(f'y val: {y_val.shape}')
    print(f'test: {test.shape}')

    # Model
    clf = xgb.XGBRegressor()
    clf.fit(X_train, y_train)
    y_val_pred = clf.predict(X_val)
    print(f'MAE: {metrics.mean_absolute_error(y_val, y_val_pred)}')

    test['pred'] = clf.predict(test)
    pred = test.join(titles, how='left').sort_values('pred', ascending=False)

    for i, row in pred.iloc[:25, :].iterrows():
        print(f'[{i}] {row["title"]}: {row["pred"]}')

    print()
    fi = sorted([(feat, imp) for feat, imp in zip(X_train.columns, clf.feature_importances_)], key=lambda x: x[1], reverse=True)
    for f, i in fi[:25]:
        print(f'{f}: {i}')