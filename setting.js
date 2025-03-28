const { createApp, ref, reactive, onMounted } = Vue;
    
    createApp({
      setup() { 
        // 响应式数据
        const contestants = ref([]);
        const selectedContestant = ref('');
        const mvpCard = ref(null);
        const matchData = reactive({
          match_code: '',
          match_week: '',
          match_day: '',
          match_num: '',
          type: '',
          series: '',
          description: '',
          team1: '',
          team2: '',
          win_team: ''
        });

        // 创建 SweetAlert2 的混合实例（在 setup 中直接创建）
        const customAlert = Swal.mixin({
          width: '400px',
          customClass: {
            popup: 'custom-swal-popup'
          }
        });

        // 提交 MVP 表单
        const submitForm = () => {
          const formData = new URLSearchParams();
          formData.append('mvp', selectedContestant.value);
          axios.post('http://127.0.0.1:1111/setMvp', formData)
            .then(response => {
              if (response.status === 204) {
                axios.get('http://127.0.0.1:1111/selectedMVP')
                  .then(res => {
                    if (res.data && res.data.msg === "请求成功") {
                      mvpCard.value = res.data.data;
                      customAlert.fire({
                        title: '提交成功',
                        text: 'MVP 选手已更新',
                        icon: 'success',
                        timer: 1500,
                        showConfirmButton: false
                      });
                    } else {
                      customAlert.fire({
                        icon: 'error',
                        title: '错误',
                        text: '获取MVP数据失败'
                      });
                    }
                  })
                  .catch(err => {
                    console.error('获取MVP数据错误：', err);
                    customAlert.fire({
                      icon: 'error',
                      title: '错误',
                      text: '获取MVP数据错误'
                    });
                  });
              } else {
                customAlert.fire({
                  icon: 'error',
                  title: '错误',
                  text: '提交失败'
                });
              }
            })
            .catch(error => {
              console.error('提交错误：', error);
              customAlert.fire({
                icon: 'error',
                title: '错误',
                text: '提交错误'
              });
            });
        };

        // 提交比赛数据
        const submitMatchData = () => {
          const formData = new URLSearchParams();
          formData.append('match_code', matchData.match_code);
          formData.append('match_week', matchData.match_week);
          formData.append('match_day', matchData.match_day);
          formData.append('match_num', matchData.match_num);
          formData.append('type', matchData.type);
          formData.append('series', matchData.series);
          formData.append('description', matchData.description);
          formData.append('team1', matchData.team1);
          formData.append('team2', matchData.team2);
          formData.append('win_team',matchData.win_team)
          axios.post('http://127.0.0.1:1111/saveMatchData', formData)
            .then(response => {
              if (response.status === 200 && response.data.message === "数据保存成功") {
                customAlert.fire({
                  icon: 'success',
                  title: '提交成功',
                  timer: 1500,
                  showConfirmButton: false
                });
              } else {
                customAlert.fire({
                  icon: 'error',
                  title: '错误',
                  text: '提交失败'
                });
              }
            })
            .catch(error => {
              console.error('提交错误：', error);
              customAlert.fire({
                icon: 'error',
                title: '错误',
                text: '提交错误'
              });
            });
        };

        // 生命周期：组件挂载后加载数据
        onMounted(() => {
          // 加载选手列表
          axios.get('http://127.0.0.1:1111/player_list')
            .then(response => {
              contestants.value = response.data.data;
            })
            .catch(error => {
              console.error('获取选手列表失败：', error);
            });
          // 获取队名数据
          axios.get('http://127.0.0.1:1111/teamNames')
            .then(response => {
              matchData.team1 = response.data.data.team1;
              matchData.team2 = response.data.data.team2;
            })
            .catch(error => {
              console.error('获取队名失败：', error);
            });
        });

        return {
          contestants,
          selectedContestant,
          mvpCard,
          matchData,
          submitForm,
          submitMatchData
        };
      }
    }).mount('#app');