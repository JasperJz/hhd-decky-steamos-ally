(function (D, R) {
  'use strict';
  const h = R.createElement;
  const shortcutAppType = 1073741824;

  return D.definePlugin(() => {
    const steam = globalThis.SteamClient;
    const ui = () => globalThis.SteamUIStore || D.Router;

    function AchievementList({appId}) {
      const [state, setState] = R.useState({});
      const [attempt, retry] = R.useState(0);
      const [showUnlocked, selectUnlocked] = R.useState(false);
      R.useEffect(() => {
        let cancelled = false;
        let timeout;
        setState({});
        async function load() {
          try {
            const response = await Promise.race([
              steam.Apps.GetMyAchievementsForApp(String(appId)),
              new Promise((_, reject) => {
                timeout = setTimeout(() => reject(new Error('Steam timed out')), 10000);
              }),
            ]);
            const rows = response?.data?.rgAchievements;
            if (response?.result !== 1 || !Array.isArray(rows)) throw new Error('Steam request failed');
            if (!cancelled) setState({rows});
          } catch {
            if (!cancelled) setState({error: true});
          } finally {
            clearTimeout(timeout);
          }
        }
        load();
        return () => {
          cancelled = true;
          clearTimeout(timeout);
        };
      }, [appId, attempt]);

      let content = h('p', {role: 'status'}, '正在读取 Steam 成就…');
      if (state.error) {
        content = h(D.DialogButton, {onClick: () => retry(attempt + 1)}, '成就读取失败 · 重试');
      } else if (state.rows) {
        const rows = state.rows;
        const unlocked = rows.filter(row => row.bAchieved).length;
        const visibleRows = rows.filter(row => Boolean(row.bAchieved) === showUnlocked);
        content = rows.length ? h('div', null,
          h('p', null, `已解锁 ${unlocked} / ${rows.length}`),
          h('progress', {value: unlocked, max: rows.length, style: {width: '100%'}}),
          h(D.Focusable, {flow: 'horizontal', style: {display: 'flex', gap: 6, margin: '8px 0'}},
            ...[false, true].map(isUnlocked => h(D.DialogButton, {
              key: String(isUnlocked),
              'aria-pressed': showUnlocked === isUnlocked,
              onClick: () => selectUnlocked(isUnlocked),
              style: {
                flex: '1 1 0', minWidth: 0, padding: '6px 4px',
                boxShadow: showUnlocked === isUnlocked ? 'inset 0 -3px #1a9fff' : undefined,
              },
            }, isUnlocked ? `已解锁 ${unlocked}` : `未解锁 ${rows.length - unlocked}`))),
          !visibleRows.length && h('p', null, showUnlocked ? '还没有解锁成就。' : '所有成就均已解锁。'),
          h(D.Focusable, null,
            ...visibleRows.map(row => {
              const status = row.bAchieved ? '已解锁' : '未解锁';
              const progress = !row.bAchieved && row.flMaxProgress > row.flMinProgress
                ? ` · ${row.flCurrentProgress} / ${row.flMaxProgress}` : '';
              return h(D.Focusable, {
                key: row.strID, focusable: true,
                style: {display: 'flex', gap: 12, padding: '8px 4px'},
              },
              row.strImage && h('img', {src: row.strImage, alt: '', width: 40, height: 40, loading: 'lazy'}),
              h('div', null,
                h('strong', null, row.strName || '未提供名称'),
                h('div', null, status + progress),
                row.strDescription && h('div', null, row.strDescription)));
            }))) : h('p', null, '这款游戏没有 Steam 成就。');
      }
      return content;
    }

    function Content() {
      const [revision, refresh] = R.useState(0);
      const store = ui();
      const game = store?.MainRunningApp;
      const appId = Number(game?.appid ?? store?.MainRunningAppID);
      const running = Number.isSafeInteger(appId) && appId > 0;
      const shortcut = game?.app_type === shortcutAppType || game?.canonicalAppType === shortcutAppType;
      return h(D.PanelSection, {title: game?.display_name || '当前游戏成就'},
        h(D.PanelSectionRow, null, h(D.DialogButton, {onClick: () => refresh(revision + 1)}, '刷新成就')),
        !running ? h('p', null, '请先启动一款 Steam 游戏。')
          : shortcut ? h('p', null, '非 Steam 游戏没有可读取的 Steam 成就。')
            : h(AchievementList, {key: appId + ':' + revision, appId}));
    }

    return {
      title: h('div', {className: D.staticClasses.Title}, 'Quick Achievements'),
      icon: h('span', {'aria-hidden': true}, '🏆'),
      content: h(Content),
    };
  });
})(DFL, SP_REACT);
