import streamlit as st
import random
import time
from datetime import datetime, timedelta
import pandas as pd
import json
import os
from supabase import create_client, Client
import uuid

# Page setup
st.set_page_config(
    page_title="食谱转盘",
    page_icon="🚥",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Supabase setup
@st.cache_resource
def init_supabase():
    SUPABASE_URL = st.secrets.get("SUPABASE_URL", "YOUR_SUPABASE_URL")
    SUPABASE_KEY = st.secrets.get("SUPABASE_ANON_KEY", "YOUR_SUPABASE_ANON_KEY")
    
    if SUPABASE_URL == "YOUR_SUPABASE_URL" or SUPABASE_KEY == "YOUR_SUPABASE_ANON_KEY":
        st.error("Please configure Supabase connection with URL and ANON_KEY")
        return None
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return supabase
    except Exception as e:
        st.error(f"Supabase connection failed: {e}")
        return None

# TODO
# Randomized user id for each session
# this needs to change for scaling
def get_user_id():
    if 'user_id' not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    return st.session_state.user_id

# Database management 
class DatabaseManager:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.user_id = get_user_id()
    
    def load_all_foods(self):
        try:
            # get 'system' foods and current user foods
            result = self.supabase.table('foods').select('*').in_(
                'user_id', ['system', self.user_id]
            ).execute()
            
            foods_by_category = {}
            
            for item in result.data:
                category = item['category']
                food_name = item['food_name']
                user_id = item['user_id']
                
                if category not in foods_by_category:
                    foods_by_category[category] = []
                
                foods_by_category[category].append({
                    'name': food_name,
                    'is_custom': user_id != 'system',
                    'id': item.get('id')
                })
            
            return foods_by_category
        except Exception as e:
            st.error(f"Failed to add food: {e}")
            return {}
    
    def get_categories(self):
        try:
            result = self.supabase.table('foods').select('category').execute()
            categories = list(set(item['category'] for item in result.data))
            return sorted(categories)
        except Exception as e:
            st.error(f"Failed to get categories: {e}")
            return []
    
    def add_food(self, category, food_name):
        try:
            # check if food already exists
            existing = self.supabase.table('foods').select('*').eq(
                'category', category
            ).eq('food_name', food_name).in_(
                'user_id', ['system', self.user_id]
            ).execute()
            
            if existing.data:
                return False, "食材已存在"
            
            # add new food
            data = {
                # TODO
                # 'user_id': self.user_id,
                'user_id': 'system',  # currently we are making all user 'system' for single user mode
                'category': category,
                'food_name': food_name,
                'created_at': datetime.now().isoformat()
            }
            result = self.supabase.table('foods').insert(data).execute()
            return True, "添加成功"
        except Exception as e:
            return False, f"添加失败: {e}"
    
    # TODO
    def delete_food(self, food_id):
        """Delete food (only those added by user)"""
        try:
            result = self.supabase.table('foods').delete().eq(
                'id', food_id
            ).eq('user_id', self.user_id).execute()
            return True
        except Exception as e:
            st.error(f"Failed to delete food: {e}")
            return False
    
    # TODO
    def clear_user_foods(self):
        """Clear user defined food"""
        try:
            result = self.supabase.table('foods').delete().eq('user_id', self.user_id).execute()
            return True
        except Exception as e:
            st.error(f"清空食材失败: {e}")
            return False
    
    def load_week_plans(self):
        try:
            # result = self.supabase.table('week_plans').select('*').eq('user_id', self.user_id).order('created_at', desc=True).execute()
            result = self.supabase.table('week_plans').select('*').eq('user_id', 'system').order('created_at', desc=True).execute()

            plans = []
            for item in result.data:
                plans.append({
                    'id': item['id'],
                    '日期': item['plan_date'],
                    '时间': item['plan_time'],
                    '食材': json.loads(item['foods_data'])
                })
            return plans
        except Exception as e:
            st.error(f"加载周计划失败: {e}")
            return []
    
    def save_week_plan(self, foods_data):
        try:
            data = {
                'user_id': 'system',
                'plan_date': datetime.now().strftime("%Y-%m-%d"),
                'plan_time': datetime.now().strftime("%H:%M"),
                'foods_data': json.dumps(foods_data, ensure_ascii=False),
                'created_at': datetime.now().isoformat()
            }
            result = self.supabase.table('week_plans').insert(data).execute()
            return True
        except Exception as e:
            st.error(f"Failed to save week plan: {e}")
            return False
    
    def clear_week_plans(self):
        try:
            result = self.supabase.table('week_plans').delete().eq('user_id', 'system').execute()
            return True
        except Exception as e:
            st.error(f"Failed to clear week plan: {e}")
            return False

# css styling
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #2E8B57;
        font-size: 2.5rem;
        margin-bottom: 2rem;
    }
    .category-header {
        background: linear-gradient(90deg, #4CAF50, #45a049);
        color: white;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        margin: 10px 0;
        font-weight: bold;
    }
    .food-item {
        background-color: #f0f8ff;
        padding: 8px 12px;
        margin: 5px;
        border-radius: 15px;
        display: inline-block;
        border-left: 4px solid #4CAF50;
        font-size: 14px;
    }
    .custom-food-item {
        background-color: #fff3cd;
        padding: 8px 12px;
        margin: 5px;
        border-radius: 15px;
        display: inline-block;
        border-left: 4px solid #ffc107;
        font-size: 14px;
    }
    .selected-food {
        background: linear-gradient(45deg, #FFD700, #FFA500);
        color: #333;
        font-weight: bold;
        animation: pulse 1s ease-in-out;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    .cloud-status {
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown('<h1 class="main-header">🚥 健康食谱转盘</h1>', unsafe_allow_html=True)
    
    # Initialize Supabase
    supabase = init_supabase()
    if not supabase:
        st.stop()

    db = DatabaseManager(supabase)
    
    # Cloud status display
    st.markdown(f'''
    <div class="cloud-status">
        ☁️ 已连接云数据库 | 用户ID: {get_user_id()[:8]}... | 数据实时同步
    </div>
    ''', unsafe_allow_html=True)
    
    # Initialize session state
    if 'spinning' not in st.session_state:
        st.session_state.spinning = False
    if 'selected_foods' not in st.session_state:
        st.session_state.selected_foods = {}
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    if 'foods_data' not in st.session_state:
        st.session_state.foods_data = {}
    
    # Load initial food from database
    if not st.session_state.data_loaded:
        with st.spinner("正在从云端加载数据..."):
            st.session_state.foods_data = db.load_all_foods()
            st.session_state.week_plan = db.load_week_plans()
            st.session_state.categories = db.get_categories()
        st.session_state.data_loaded = True

    tab1, tab2, tab3, tab4 = st.tabs(["🎯 转盘选择", "📅 本周计划", "🍽️ 食材库", "➕ 添加食材"])
    
    with tab1:
        st.markdown("### 🎲 转转盘，选择本周的健康食材！")
        
        if not st.session_state.categories:
            st.warning("⚠️ 数据库中没有食材，请先添加一些食材！")
            return
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            selected_categories = st.multiselect(
                "选择要转盘的食材类别：",
                st.session_state.categories,
                default=['🌾 碳水','🥩 蛋白质','🥬 蔬菜']
            )
        
        with col2:
            spin_button = st.button("🎯 开始转盘", type="primary")
        
        if spin_button and selected_categories:
            st.session_state.spinning = True
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            selected_foods = {}
            
            for i, category in enumerate(selected_categories):
                status_text.text(f"正在选择 {category}...")
                
                # Get all foods from selected category
                category_foods = st.session_state.foods_data.get(category, [])
                if not category_foods:
                    st.warning(f"类别 {category} 中没有食材！")
                    continue
                
                food_names = [food['name'] for food in category_foods]
                
                # Simulate spinning wheel
                for j in range(10):
                    temp_food = random.choice(food_names)
                    status_text.text(f"{category}: {temp_food}")
                    time.sleep(0.1)
                    progress_bar.progress((i * 10 + j + 1) / (len(selected_categories) * 10))
                
                # Pick food with randomization
                selected_food = random.choice(food_names)
                selected_foods[category] = selected_food
                
            st.session_state.selected_foods = selected_foods
            st.session_state.spinning = False

            progress_bar.empty()
            status_text.empty()
            
            # display result
            st.success("🎉 转盘完成！本次选中的食材：")
            
        if st.session_state.selected_foods:
            cols = st.columns(len(st.session_state.selected_foods))
            for i, (category, food) in enumerate(st.session_state.selected_foods.items()):
                with cols[i]:
                    st.markdown(f"""
                    <div style="text-align: center; padding: 20px; 
                                border-radius: 15px; margin: 10px; color: #333;">
                        <h4>{category}</h4>
                        <h3>{food}</h3>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Add to week plan button
            if st.button("📅 添加到本周计划"):
                if db.save_week_plan(dict(st.session_state.selected_foods)):
                    # reload for the most updated week plan
                    st.session_state.week_plan = db.load_week_plans()
                    st.success("✅ 已添加到本周计划并同步到云端！")
                else:
                    st.error("❌ 保存失败，请检查网络连接")
    
    with tab2:
        st.markdown("### 📅 本周食材计划")
        
        # Refresh button
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("从云端同步的所有计划：")
        with col2:
            if st.button("🔄 刷新"):
                st.session_state.week_plan = db.load_week_plans()
                st.success("已刷新数据！")
        
        if st.session_state.week_plan:
            # 清空计划按钮
            if st.button("🗑️ 清空所有计划"):
                if db.clear_week_plans():
                    st.session_state.week_plan = []
                    st.success("计划已清空并同步到云端！")
                else:
                    st.error("清空失败，请检查网络连接")
            
            # 显示计划
            for i, plan in enumerate(st.session_state.week_plan):
                with st.expander(f"计划 {i+1} - {plan['日期']} {plan['时间']}", expanded=True):
                    cols = st.columns(len(plan['食材']))
                    for j, (category, food) in enumerate(plan['食材'].items()):
                        with cols[j]:
                            st.markdown(f"""
                            <div class="food-item selected-food">
                                <strong>{category}</strong><br>
                                {food}
                            </div>
                            """, unsafe_allow_html=True)
        else:
            st.info("📝 还没有制定计划，去转盘页面选择一些食材吧！")
    
    with tab3:
        st.markdown("### 🍽️ 食材库")
        
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 刷新食材库"):
                st.session_state.foods_data = db.load_all_foods()
                st.session_state.categories = db.get_categories()
                st.success("食材库已刷新！")
        
        if not st.session_state.foods_data:
            st.info("📝 食材库为空，请在'添加食材'页面添加一些食材！")
            return
        
        # 显示所有食材
        for category, foods in st.session_state.foods_data.items():
            st.markdown(f'<div class="category-header">{category}</div>', unsafe_allow_html=True)
            
            # 以网格形式显示食材
            cols = st.columns(4)
            for i, food_info in enumerate(foods):
                with cols[i % 4]:
                    food_name = food_info['name']
                    is_custom = food_info['is_custom']
                    food_id = food_info['id']
                    
                    if not is_custom:
                        # 系统食材
                        st.markdown(f'<div class="food-item">{food_name} </div>', unsafe_allow_html=True)
                    else:
                        # 用户自定义食材，有删除按钮
                        food_col, del_col = st.columns([3, 1])
                        with food_col:
                            st.markdown(f'<div class="custom-food-item">{food_name} ☁️</div>', unsafe_allow_html=True)
                        with del_col:
                            if st.button("🗑️", key=f"del_{food_id}", help=f"删除 {food_name}"):
                                if db.delete_food(food_id):
                                    # 重新加载数据
                                    st.session_state.foods_data = db.load_all_foods()
                                    st.success(f"已删除 {food_name}")
                                    st.rerun()
                                else:
                                    st.error("删除失败")
            
            st.markdown("<br>", unsafe_allow_html=True)
        
        # 食材统计
        total_system = sum(1 for foods in st.session_state.foods_data.values() for food in foods if not food['is_custom'])
        total_custom = sum(1 for foods in st.session_state.foods_data.values() for food in foods if food['is_custom'])
        total_foods = total_system + total_custom
        
        st.markdown(f"""
        <div style="text-align: center; padding: 20px; background: #e8f5e8; border-radius: 10px; margin: 20px 0;">
            <h3>📊 食材库统计</h3>
            <p>系统食材：<strong>{total_system}</strong> 种 | 用户自定义：<strong>{total_custom}</strong> 种</p>
            <p>总共有 <strong>{total_foods}</strong> 种健康食材</p>
            <p>涵盖 <strong>{len(st.session_state.categories)}</strong> 个营养类别</p>
        </div>
        """, unsafe_allow_html=True)
    
    with tab4:
        st.markdown("### ➕ 添加自定义食材")
        st.markdown("在这里添加您喜欢的健康食材，数据会自动同步到云端！")
        
        # Batch add
        st.markdown("#### 🚀 批量添加")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # select from existing categories or start a new category
            category_option = st.radio("类别选择方式", ["选择现有类别", "创建新类别"])
            
            if category_option == "选择现有类别":
                if st.session_state.categories:
                    batch_category = st.selectbox("选择类别", st.session_state.categories, key="batch_category")
                else:
                    st.warning("没有现有类别，请先创建新类别")
                    batch_category = st.text_input("新类别名称", key="new_batch_category")
            else:
                batch_category = st.text_input("新类别名称（如：🥗 沙拉类）", key="new_batch_category")
            
            batch_foods = st.text_area(
                "批量添加食材（每行一个）", 
                placeholder="例如：\n紫薯叶\n芦笋\n西兰花",
                height=100
            )
        
        with col2:
            st.markdown("<br><br><br>", unsafe_allow_html=True)
            if st.button("📦 批量添加", type="primary"):
                if batch_foods.strip() and batch_category.strip():
                    new_foods = [food.strip() for food in batch_foods.strip().split('\n') if food.strip()]
                    added_count = 0
                    duplicate_count = 0
                    failed_count = 0
                    
                    with st.spinner("正在上传到云端..."):
                        for food in new_foods:
                            success, message = db.add_food(batch_category.strip(), food)
                            if success:
                                added_count += 1
                            elif "已存在" in message:
                                duplicate_count += 1
                            else:
                                failed_count += 1
                    
                    # refreshing data
                    if added_count > 0:
                        st.session_state.foods_data = db.load_all_foods()
                        st.session_state.categories = db.get_categories()
                    
                    # result display
                    if added_count > 0:
                        st.success(f"✅ 成功添加 {added_count} 种食材到 {batch_category}")
                    if duplicate_count > 0:
                        st.warning(f"⚠️ {duplicate_count} 种食材已存在，已跳过")
                    if failed_count > 0:
                        st.error(f"❌ {failed_count} 种食材添加失败")
                else:
                    st.error("请填写类别和食材名称")
        
        st.markdown("---")
        
        # adding a single food
        st.markdown("#### 🎯 精准添加")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            single_food_name = st.text_input("食材名称", placeholder="输入食材名称")
        
        with col2:
            # select from existing categories or start a new category
            single_category_option = st.radio("类别选择", ["现有类别", "新类别"], key="single_cat_option")
            
            if single_category_option == "现有类别":
                if st.session_state.categories:
                    single_food_category = st.selectbox("选择类别", st.session_state.categories, key="single_category")
                else:
                    single_food_category = st.text_input("新类别名称", key="single_new_category")
            else:
                single_food_category = st.text_input("新类别名称", key="single_new_category2")
        
        with col3:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("✅ 添加", key="single_add"):
                if single_food_name.strip() and single_food_category.strip():
                    with st.spinner("正在保存到云端..."):
                        success, message = db.add_food(single_food_category.strip(), single_food_name.strip())
                        if success:
                            # refreshing data
                            st.session_state.foods_data = db.load_all_foods()
                            st.session_state.categories = db.get_categories()
                            st.success(f"✅ {message}：'{single_food_name}' 已添加到 {single_food_category}")
                        else:
                            if "已存在" in message:
                                st.warning(f"⚠️ {message}")
                            else:
                                st.error(f"❌ {message}")
                else:
                    st.error("请填写食材名称和类别")
        
        st.markdown("---")
        
        # TODO manage user-added food
        st.markdown("#### 🛠️ 管理我的食材")
        
        user_foods = {category: [food for food in foods if food['is_custom']] 
                     for category, foods in st.session_state.foods_data.items()}
        user_foods = {k: v for k, v in user_foods.items() if v}  # 过滤空类别
        
        if user_foods:
            for category, foods in user_foods.items():
                with st.expander(f"{category} - {len(foods)} 种自定义食材"):
                    cols = st.columns(3)
                    for i, food_info in enumerate(foods):
                        food_name = food_info['name']
                        food_id = food_info['id']
                        with cols[i % 3]:
                            food_col, del_col = st.columns([3, 1])
                            with food_col:
                                st.write(f"☁️ {food_name}")
                            with del_col:
                                if st.button("删除", key=f"manage_del_{food_id}"):
                                    if db.delete_food(food_id):
                                        st.session_state.foods_data = db.load_all_foods()
                                        st.success("已从云端删除")
                                        st.rerun()
                                    else:
                                        st.error("删除失败")
            
            # 清空所有用户食材
            st.markdown("#### 🧹 清理选项")
            
            if st.button("🗑️ 清空我的所有食材", help="这将删除所有您添加的食材"):
                if st.checkbox("我确认要清空所有自定义食材", key="confirm_clear"):
                    with st.spinner("正在从云端删除..."):
                        if db.clear_user_foods():
                            # 重新加载数据
                            st.session_state.foods_data = db.load_all_foods()
                            st.session_state.categories = db.get_categories()
                            st.success("🧹 已清空所有自定义食材")
                            st.rerun()
                        else:
                            st.error("清空失败，请检查网络连接")
        else:
            st.info("您还没有添加任何自定义食材")
        
        # 云端状态显示
        st.markdown("---")
        
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 20px;">
        <p>🌱 健康饮食，从每一餐开始</p>
        <p><small>💡 提示：建议每周选择不同的食材搭配，保持营养均衡</small></p>
        <p><small>☁️ 您的数据已安全保存在云端，支持多设备同步！</small></p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()