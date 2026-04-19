"""
特别提示：策略示例仅供学习参考，不可直接用于实盘，否则后果自负。
"""

import os
import argparse
import pickle
import random
import pandas as pd
import numpy as np
import xgboost as xgb
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# 尝试导入绘图库
try:
    import matplotlib.pyplot as plt
    HAS_PLT = True
except ImportError:
    HAS_PLT = False
    print("未安装 matplotlib，无法绘制净值曲线。建议安装：pip install matplotlib")

# ==================== 因子计算函数 ====================
def calculate_indicators(df):
    """
    计算所有技术指标（使用 pandas/numpy 向量化）
    因子列表：
    1. MA (5, 10, 20, 60)
    2. MACD (DIF, DEA, HIST)
    3. EXPMA (EMA12, EMA26)
    4. KDJ (K, D, J)
    5. RSI (14)
    6. WR (14)
    7. VOL (成交量)
    8. VR (26)
    9. BOLL (中轨, 标准差, 上轨, 下轨)
    10. LWR (LWR1, LWR2)
    11. BIAS (5, 10, 20)
    12. PSY (12)
    13. 影线/实体比 (shadow_body_ratio)
    14. 收盘位置 (close_position)
    15. 波动成交量 (volatility_volume)
    """
    df = df.copy()
    df = df.sort_values('stime').reset_index(drop=True)

    # 1. 移动平均线 MA
    for length in [5, 10, 20, 60]:
        df[f'MA_{length}'] = df['close'].rolling(window=length, min_periods=1).mean()

    # 2. MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_hist'] = df['MACD'] - df['MACD_signal']

    # 3. 指数移动平均 EXPMA
    df['EMA_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['close'].ewm(span=26, adjust=False).mean()

    # 4. KDJ 指标
    n = 9
    m1 = 3
    m2 = 3
    low_n = df['low'].rolling(window=n, min_periods=1).min()
    high_n = df['high'].rolling(window=n, min_periods=1).max()
    rsv = (df['close'] - low_n) / (high_n - low_n + 1e-10) * 100
    df['K'] = rsv.ewm(com=m1-1, adjust=False).mean()
    df['D'] = df['K'].ewm(com=m2-1, adjust=False).mean()
    df['J'] = 3 * df['K'] - 2 * df['D']

    # 5. 相对强弱指标 RSI
    def rsi(series, length=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=length, min_periods=length).mean()
        avg_loss = loss.rolling(window=length, min_periods=length).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (1 + rs))
    df['RSI_14'] = rsi(df['close'], 14)

    # 6. 威廉指标 WR
    high_14 = df['high'].rolling(window=14, min_periods=1).max()
    low_14 = df['low'].rolling(window=14, min_periods=1).min()
    df['WR_14'] = (high_14 - df['close']) / (high_14 - low_14 + 1e-10) * -100

    # 7. 成交量 VOL
    df['VOL'] = df['volume']

    # 8. 成交量比率 VR
    length = 26
    up_vol = df['volume'].where(df['close'] > df['close'].shift(1), 0)
    down_vol = df['volume'].where(df['close'] < df['close'].shift(1), 0)
    up_sum = up_vol.rolling(window=length, min_periods=1).sum()
    down_sum = down_vol.rolling(window=length, min_periods=1).sum()
    df['VR_26'] = (up_sum / (down_sum + 1e-10)) * 100

    # 9. 布林带 BOLL
    length = 20
    std = 2
    df['BOLL_mid'] = df['close'].rolling(window=length, min_periods=1).mean()
    df['BOLL_std'] = df['close'].rolling(window=length, min_periods=1).std()
    df['BOLL_upper'] = df['BOLL_mid'] + std * df['BOLL_std']
    df['BOLL_lower'] = df['BOLL_mid'] - std * df['BOLL_std']

    # 10. LWR 指标
    N = 9
    M1 = 3
    rolling_high = df['high'].rolling(window=N, min_periods=1).max()
    rolling_low = df['low'].rolling(window=N, min_periods=1).min()
    lwr1 = (rolling_high - df['close']) / (rolling_high - rolling_low + 1e-10) * 100
    df['LWR1'] = lwr1
    df['LWR2'] = lwr1.rolling(window=M1, min_periods=1).mean()

    # 11. 乖离率 BIAS
    for length in [5, 10, 20]:
        sma = df['close'].rolling(window=length, min_periods=1).mean()
        df[f'BIAS_{length}'] = (df['close'] - sma) / sma * 100

    # 12. 心理线 PSY
    length = 12
    up = (df['close'].shift(1) < df['close']).astype(int)
    df['PSY_12'] = up.rolling(window=length, min_periods=length).mean() * 100

    # 13. 影线/实体比：上影线+下影线 与 实体长度之比
    body = (df['close'] - df['open']).abs()
    up_shadow = df['high'] - np.maximum(df['close'], df['open'])
    down_shadow = np.minimum(df['close'], df['open']) - df['low']
    df['shadow_body_ratio'] = (up_shadow + down_shadow) / (body + 1e-10)

    # 14. 收盘位置：收盘价在当日振幅区间的位置比例 [0,1]
    df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-10)

    # 15. 波动成交量：相对振幅 × 成交量（量价结合）
    rel_amplitude = (df['high'] - df['low']) / (df['close'] + 1e-10)
    df['volatility_volume'] = rel_amplitude * df['volume']

    return df

def process_file(file_path, code, calc_mode, cache_dir):
    """
    处理单个文件，支持缓存。
    返回处理后的DataFrame（包含所有列）和特征列列表。
    """
    cache_file = os.path.join(cache_dir, f"{code}.pkl")

    need_recalc = False
    if calc_mode == 'full':
        need_recalc = True
    elif calc_mode == 'cache_only':
        if not os.path.exists(cache_file):
            raise FileNotFoundError(f"缓存文件 {cache_file} 不存在，且模式为 cache_only")
        need_recalc = False
    else:  # auto
        if os.path.exists(cache_file):
            raw_mtime = os.path.getmtime(file_path)
            cache_mtime = os.path.getmtime(cache_file)
            if raw_mtime > cache_mtime:
                need_recalc = True
        else:
            need_recalc = True

    if not need_recalc:
        df = pd.read_pickle(cache_file)
        feature_cols = [c for c in df.columns if c not in ['stime', 'open', 'high', 'low', 'close', 'volume', 'amount', 'next_close', 'label']]
        return df, feature_cols

    # 重新计算
    df_raw = pd.read_csv(file_path)
    df_raw['stime'] = df_raw['stime'].astype(int)
    df = calculate_indicators(df_raw)

    df['next_close'] = df['close'].shift(-1)
    df['label'] = (df['next_close'] > df['close']).astype(int)
    df = df.dropna(subset=['label']).reset_index(drop=True)

    feature_cols = [c for c in df.columns if c not in ['stime', 'open', 'high', 'low', 'close', 'volume', 'amount', 'next_close', 'label']]
    df = df.dropna(subset=feature_cols).reset_index(drop=True)

    os.makedirs(cache_dir, exist_ok=True)
    df.to_pickle(cache_file)

    return df, feature_cols

def load_benchmark(index_file):
    """
    加载沪深300指数基准数据，返回一个字典，键为日期（整数），值为日收益率。
    使用前向填充确保所有日期都有收益率。
    """
    df = pd.read_csv(index_file)
    # 筛选沪深300指数代码 000300.SH
    df_bench = df[df['ts_code'] == '000300.SH'].copy()
    if df_bench.empty:
        print("警告：未找到沪深300指数数据，基准曲线将不可用")
        return {}
    df_bench['trade_date'] = df_bench['trade_date'].astype(int)
    df_bench = df_bench.sort_values('trade_date').reset_index(drop=True)
    # 计算日收益率
    df_bench['bench_ret'] = df_bench['close'].pct_change()
    # 填充第一天的NaN为0
    df_bench['bench_ret'].fillna(0, inplace=True)
    # 构建从最小日期到最大日期的完整日期索引
    min_date = df_bench['trade_date'].min()
    max_date = df_bench['trade_date'].max()
    all_dates = pd.date_range(start=str(min_date), end=str(max_date), freq='D')
    all_dates_int = [int(d.strftime('%Y%m%d')) for d in all_dates]
    full_df = pd.DataFrame({'trade_date': all_dates_int})
    # 合并
    full_df = full_df.merge(df_bench[['trade_date', 'bench_ret']], on='trade_date', how='left')
    # 前向填充缺失的收益率（周末、假期）
    full_df['bench_ret'] = full_df['bench_ret'].fillna(method='ffill')
    # 转换为字典
    bench_dict = dict(zip(full_df['trade_date'], full_df['bench_ret']))
    return bench_dict

def main():
    parser = argparse.ArgumentParser(description='ETF选股策略：训练或预测')
    parser.add_argument('--mode', type=str, choices=['train', 'predict'], default='train',
                        help='运行模式：train-训练并保存模型，predict-加载已有模型进行回测')
    parser.add_argument('--calc_mode', type=str, choices=['auto', 'full', 'cache_only'], default='auto',
                        help='数据预处理模式：auto-自动检测文件修改时间更新缓存，full-强制重新计算所有数据，cache_only-仅使用缓存（缓存不存在则报错）')
    parser.add_argument('--model_dir', type=str, default='models',
                        help='模型保存目录')
    parser.add_argument('--max_etfs', type=int, default=0,
                        help='最多使用的ETF数量，0表示使用全部，大于0则随机抽取该数量')
    parser.add_argument('--random_seed', type=int, default=42,
                        help='随机种子，用于可重复的ETF抽取')
    parser.add_argument('--top_n', type=int, default=30,
                        help='每日选股数量（按预测概率从高到低排序），默认为30')
    args = parser.parse_args()

    model_dir = args.model_dir
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, 'xgboost_model.json')
    feature_cols_path = os.path.join(model_dir, 'feature_cols.pkl')

    # 缓存目录
    cache_dir = "etf/etf_data/processed"
    os.makedirs(cache_dir, exist_ok=True)

    # 读取代码列表
    code_file = "etf/etf_data/etf_code.csv"
    if not os.path.exists(code_file):
        print(f"错误：未找到代码文件 {code_file}")
        return

    code_df = pd.read_csv(code_file)
    if '代码' not in code_df.columns:
        print("错误：etf_code.csv 文件中缺少 '代码' 列")
        return

    codes = code_df['代码'].dropna().astype(str).tolist()
    print(f"从 {code_file} 读取到 {len(codes)} 个ETF代码")

    # 随机选择子集
    if args.max_etfs > 0 and args.max_etfs < len(codes):
        random.seed(args.random_seed)
        codes = random.sample(codes, args.max_etfs)
        print(f"随机选择 {len(codes)} 只ETF进行训练与回测")
    else:
        print(f"使用全部 {len(codes)} 只ETF")

    print(f"数据处理模式: {args.calc_mode}")
    print(f"每日选股数量: {args.top_n}")

    data_dir = "etf/etf_data/daily"

    all_train = []
    all_test = []
    all_raw = {}
    feature_cols = None

    for code in tqdm(codes, desc="处理ETF文件"):
        file_name = f"{code}.csv"
        file_path = os.path.join(data_dir, file_name)
        if not os.path.exists(file_path):
            tqdm.write(f"警告：文件 {file_path} 不存在，跳过")
            continue

        try:
            df, cols = process_file(file_path, code, args.calc_mode, cache_dir)
            if feature_cols is None:
                feature_cols = cols
            # 划分训练/测试集
            train = df[df['stime'] < 20250601].copy()
            test = df[df['stime'] >= 20250601].copy()
            if not test.empty:
                test['code'] = code
            if not train.empty:
                all_train.append(train)
            if not test.empty:
                all_test.append(test)
            # 原始数据用于回测
            all_raw[code] = df[['stime', 'open', 'high', 'low', 'close', 'volume', 'amount']].copy()
        except Exception as e:
            tqdm.write(f"处理文件 {file_name} 时出错: {e}")
            continue

    if not all_train:
        print("没有有效的训练数据")
        return

    # 合并数据
    print("合并训练数据...")
    train_all = pd.concat(all_train, ignore_index=True)
    print("合并测试数据...")
    test_all = pd.concat(all_test, ignore_index=True) if all_test else pd.DataFrame()

    print(f"训练集样本数: {len(train_all)}")
    print(f"测试集样本数: {len(test_all)}")

    if len(test_all) == 0:
        print("没有测试数据")
        return

    # 加载基准数据
    print("加载沪深300基准数据...")
    bench_dict = load_benchmark("etf/etf_data/index_daily.csv")

    # 根据模式决定训练或加载模型
    if args.mode == 'train':
        print("训练XGBoost模型...")
        X_train = train_all[feature_cols]
        y_train = train_all['label']
        model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            objective='binary:logistic',
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )
        model.fit(X_train, y_train)
        # 保存模型和特征列
        model.save_model(model_path)
        with open(feature_cols_path, 'wb') as f:
            pickle.dump(feature_cols, f)
        print(f"模型已保存至 {model_path}")
        print(f"特征列已保存至 {feature_cols_path}")
    else:  # predict
        if not os.path.exists(model_path):
            print(f"错误：模型文件 {model_path} 不存在，请先训练模型")
            return
        if not os.path.exists(feature_cols_path):
            print(f"错误：特征列文件 {feature_cols_path} 不存在，请先训练模型")
            return
        print(f"加载模型: {model_path}")
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        with open(feature_cols_path, 'rb') as f:
            saved_feature_cols = pickle.load(f)
        # 确保特征列一致
        if set(saved_feature_cols) != set(feature_cols):
            print("警告：当前数据特征列与保存的模型特征列不一致，可能影响预测结果")
            # 使用保存的特征列重新对齐数据
            feature_cols = saved_feature_cols
            # 注意：test_all 中的特征列也需要对齐，后面会处理

    # 预测测试集
    X_test = test_all[feature_cols]
    test_all['prob'] = model.predict_proba(X_test)[:, 1]

    # 每日选股（使用 top_n 参数）
    daily_selection = {}
    for date, group in tqdm(test_all.groupby('stime'), desc="生成每日选股"):
        top = group.nlargest(args.top_n, 'prob')
        daily_selection[date] = top[['code', 'prob']].copy()

    # 回测
    dates = sorted(daily_selection.keys())
    portfolio_returns = []
    daily_return_series = []  # (日期, 策略收益率)
    bench_returns = []        # 与策略同日的基准收益率

    for t_date in tqdm(dates, desc="回测"):
        next_date = t_date + 1
        codes = daily_selection[t_date]['code'].values
        rets = []
        for code in codes:
            raw_df = all_raw.get(code)
            if raw_df is None:
                continue
            row = raw_df[raw_df['stime'] == next_date]
            if len(row) == 0:
                continue
            open_price = row['open'].values[0]
            close_price = row['close'].values[0]
            if open_price > 0:
                ret = (close_price - open_price) / open_price
                rets.append(ret)
        if rets:
            avg_ret = np.mean(rets)
            portfolio_returns.append(avg_ret)
            daily_return_series.append((next_date, avg_ret))  # 记录实际交易日期
            # 基准收益率
            bench_ret = bench_dict.get(next_date)
            if bench_ret is not None:
                bench_returns.append(bench_ret)
            else:
                # 若基准无数据，则用0填充，但一般不会发生
                bench_returns.append(0.0)

    if not portfolio_returns:
        print("没有有效的交易数据")
        return

    # 计算策略累计收益
    cum_ret = (1 + np.array(portfolio_returns)).cumprod()
    # 计算基准累计收益（对齐日期）
    bench_cum = (1 + np.array(bench_returns)).cumprod()

    # 计算绩效指标
    daily_ret = np.array(portfolio_returns)
    sharpe = np.sqrt(252) * daily_ret.mean() / daily_ret.std() if daily_ret.std() > 0 else 0
    peak = np.maximum.accumulate(cum_ret)
    max_drawdown = (cum_ret / peak - 1).min()
    # 超额收益
    excess_ret = cum_ret[-1] - bench_cum[-1]

    print("\n=== 回测结果 ===")
    print(f"策略累计收益率: {(cum_ret[-1] - 1) * 100:.2f}%")
    print(f"基准累计收益率: {(bench_cum[-1] - 1) * 100:.2f}%")
    print(f"超额收益: {excess_ret * 100:.2f}%")
    print(f"年化夏普比率: {sharpe:.4f}")
    print(f"最大回撤: {max_drawdown * 100:.2f}%")

    # 输出前10日详情
    print("\n每日选股及收益率（前10日）:")
    for i, (date, ret) in enumerate(daily_return_series[:10]):
        # 获取对应特征日（选股日）为 date-1
        feature_date = date - 1
        codes = daily_selection[feature_date]['code'].values[:5]  # 只显示前5个代码
        print(f"{feature_date} -> 次日({date})收益率: {ret*100:.2f}%, 选股: {list(codes)}")

    # 保存回测结果
    result_df = pd.DataFrame(daily_return_series, columns=['date', 'strategy_ret'])
    result_df['strategy_cum'] = cum_ret
    result_df['bench_ret'] = bench_returns
    result_df['bench_cum'] = bench_cum
    result_df.to_csv('backtest_results.csv', index=False)
    print("\n回测结果已保存至 backtest_results.csv")

    # ========== 修改：只保存最新一天的预测结果 ==========
    if daily_selection:
        # 找到最新的特征日期（选股日）
        latest_date = max(daily_selection.keys())
        latest_group = daily_selection[latest_date]

        # 1. 按日输出代码+概率（仅最新一天）
        prob_rows = []
        for _, row in latest_group.iterrows():
            prob_rows.append({'feature_date': latest_date, 'code': row['code'], 'prob': row['prob']})
        prob_df = pd.DataFrame(prob_rows)
        prob_df.to_csv('predictions_with_prob.csv', index=False)
        print("预测概率文件已保存至 predictions_with_prob.csv（仅最新一天）")
        # 打印最新一天的预测概率文件内容
        print(f"\n最新一天（{latest_date}）预测概率文件内容：")
        print(prob_df.to_string(index=False))
        print(f"共 {len(prob_df)} 条记录")

        # 2. 按日输出代码列表（仅最新一天）
        codes_str = ','.join(latest_group['code'].values)
        codes_df = pd.DataFrame({'date': [latest_date], 'codes': [codes_str]})
        codes_df.to_csv('predictions_codes.csv', index=False)
        print("预测代码列表文件已保存至 predictions_codes.csv（仅最新一天）")
        print(f"\n最新一天（{latest_date}）预测代码列表：{codes_str}")
    else:
        print("没有预测结果可保存")

    # 绘制净值曲线
    if HAS_PLT and daily_return_series:
        dates_dt = [pd.to_datetime(str(d)) for d, _ in daily_return_series]
        plt.figure(figsize=(12, 6))
        plt.plot(dates_dt, cum_ret, label='Strategy', linewidth=2)
        plt.plot(dates_dt, bench_cum, label='CSI 300', linewidth=2, linestyle='--')
        plt.title('Backtest Equity Curve')
        plt.xlabel('Date')
        plt.ylabel('Cumulative Return')
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        plt.savefig('equity_curve.png', dpi=300, bbox_inches='tight')
        print("净值曲线已保存至 equity_curve.png")
        # 显示图形
        plt.show()
    elif not HAS_PLT:
        print("未安装 matplotlib，跳过净值曲线绘制。")

if __name__ == "__main__":
    main()
