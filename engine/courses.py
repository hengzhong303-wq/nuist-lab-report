# -*- coding: utf-8 -*-
"""南京信息工程大学课程知识库。

覆盖：
- C语言程序设计（实验1~6：语法基础/程序控制结构/函数/数组/指针/结构体）
- 工程制图（AutoCAD 上机实验）
- 通用兜底

依据真实模板结构设计：
- C语言报告：模板已含"实验目的/实验内容"，学生填
  "3．实验步骤和实验结果"（每题： （N）+ 代码截图 + 运行结果）和"4．分析与讨论"
- 工程制图报告：填页眉信息、"三、实验步骤"（N.M、小标题 + 步骤： + 截图）、"四、实验结果"
"""
import re

# =====================================================================
# C 语言：任务描述关键词 → 可编译运行的代码模板
# =====================================================================

C_PATTERNS = [
    {
        'pat': r'成绩|等级',
        'title': '成绩等级转换（if + switch 分支）',
        'stdin': '85\n',
        'code': '''#include <stdio.h>
int main()
{
    int score = 0;
    char level;
    printf("请输入成绩: ");
    scanf("%d", &score);
    if (score > 100 || score < 0)
        printf("成绩无效，请重新输入\\n");
    else
    {
        switch (score / 10)
        {
        case 10:
        case 9:  level = 'A'; break;
        case 8:  level = 'B'; break;
        case 7:  level = 'C'; break;
        case 6:  level = 'D'; break;
        default: level = 'E'; break;
        }
        printf("你的成绩%d分对应的等级为%c\\n", score, level);
    }
    return 0;
}''',
        'explain': '输入百分制成绩，若越界输出出错信息；否则用 switch(score/10) 把分数段映射为等级 A~E 并输出。',
    },
    {
        'pat': r'偶数.*数码|数码.*偶|偶数位',
        'title': '提取长整型数偶数数码重组新数',
        'stdin': '87653142\n',
        'code': '''#include <stdio.h>
int main()
{
    long s, t = 0;
    long pos = 1;
    int d;
    printf("请输入一个长整型数: ");
    scanf("%ld", &s);
    if (s < 0) s = -s;
    while (s > 0)
    {
        d = s % 10;          /* 取最低位 */
        if (d % 2 == 0)
        {
            t = t + d * pos; /* 偶数数码按原权重累加 */
            pos *= 10;
        }
        s = s / 10;          /* 丢弃最低位 */
    }
    printf("新数 t = %ld\\n", t);
    return 0;
}''',
        'explain': '用 %10 取最低位、/10 丢最低位，配合权值变量 pos 从低位向高位扫描，把偶数数码按原位置权重重组为新数 t。',
    },
    {
        'pat': r'素数',
        'title': '统计 101~200 之间的素数个数',
        'code': '''#include <stdio.h>
#include <math.h>
int main()
{
    int i, n, k = 0, flag;
    for (i = 101; i <= 200; i += 2)   /* 偶数必非素数，直接跳过 */
    {
        flag = 1;
        for (n = 2; n <= (int)sqrt((double)i); n++)
        {
            if (i % n == 0)
            {
                flag = 0;
                break;
            }
        }
        if (flag)
        {
            printf("%d ", i);
            k++;
        }
    }
    printf("\\n101~200 之间共有 %d 个素数\\n", k);
    return 0;
}''',
        'explain': '外层循环只遍历奇数（步长 2），内层用 sqrt(i) 以内的数试除并用 break 提前退出，统计并输出全部素数。',
    },
    {
        'pat': r'杨辉',
        'title': '输出杨辉三角形（二维数组）',
        'code': '''#include <stdio.h>
int main()
{
    int a[10][10] = {0};
    int i, j, n = 10;
    for (i = 0; i < n; i++)
    {
        a[i][0] = 1;
        a[i][i] = 1;
        for (j = 1; j < i; j++)
            a[i][j] = a[i - 1][j - 1] + a[i - 1][j];
    }
    for (i = 0; i < n; i++)
    {
        for (j = 0; j <= i; j++)
            printf("%6d", a[i][j]);
        printf("\\n");
    }
    return 0;
}''',
        'explain': '利用递推关系 a[i][j] = a[i-1][j-1] + a[i-1][j] 生成杨辉三角，按 %6d 格式打印成金字塔形状。',
    },
    {
        'pat': r'冒泡|排序测试',
        'title': '冒泡排序及其测试用例',
        'code': '''#include <stdio.h>
int main()
{
    int a[100], n, i, j, t;
    printf("请输入数据个数 n: ");
    scanf("%d", &n);
    printf("请输入 %d 个整数: ", n);
    for (i = 0; i < n; i++)
        scanf("%d", &a[i]);
    for (i = 0; i < n - 1; i++)          /* 共 n-1 趟 */
        for (j = 0; j < n - 1 - i; j++)  /* 每趟比较到未排序部分末尾 */
            if (a[j] > a[j + 1])
            {
                t = a[j]; a[j] = a[j + 1]; a[j + 1] = t;
            }
    printf("排序结果: ");
    for (i = 0; i < n; i++)
        printf("%d ", a[i]);
    printf("\\n");
    return 0;
}''',
        'stdin': '8\n5 9 1 8 3 7 2 6\n',
        'explain': '设计正序、逆序、含重复元素、含负数等多组测试用例验证冒泡排序；程序读入 n 个整数并输出升序结果。',
    },
    {
        'pat': r'二维数组.*地址|地址.*存储|3\s*[×xX]\s*5',
        'title': '打印 3×5 二维数组各元素地址',
        'code': '''#include <stdio.h>
int main()
{
    int a[3][5];
    int i, j;
    for (i = 0; i < 3; i++)
        for (j = 0; j < 5; j++)
            printf("&a[%d][%d] = %p\\n", i, j, (void *)&a[i][j]);
    return 0;
}''',
        'explain': '输出各元素地址可以看出：二维数组按行优先顺序存储，同一行元素地址依次递增 4 字节，行末与下一行行首地址连续。',
    },
    {
        'pat': r'选择法|选择排序',
        'title': '选择法排序',
        'code': '''#include <stdio.h>
int main()
{
    int a[10] = {3, 1, 4, 1, 5, 9, 2, 6, 5, 3};
    int i, j, k, t, n = 10;
    for (i = 0; i < n - 1; i++)
    {
        k = i;
        for (j = i + 1; j < n; j++)
            if (a[j] < a[k]) k = j;
        if (k != i)
        {
            t = a[i]; a[i] = a[k]; a[k] = t;
        }
    }
    for (i = 0; i < n; i++)
        printf("%d ", a[i]);
    printf("\\n");
    return 0;
}''',
        'explain': '每一趟在未排序区间选出最小元素与区间首元素交换，共 n-1 趟完成升序排序。',
    },
    {
        'pat': r'水仙花',
        'title': '输出水仙花数',
        'code': '''#include <stdio.h>
int main()
{
    int i, a, b, c;
    for (i = 100; i <= 999; i++)
    {
        a = i / 100;
        b = i / 10 % 10;
        c = i % 10;
        if (a * a * a + b * b * b + c * c * c == i)
            printf("%d ", i);
    }
    printf("\\n");
    return 0;
}''',
        'explain': '三位数的百、十、个位立方和等于其本身的数称为水仙花数，枚举 100~999 判断输出。',
    },
    {
        'pat': r'闰年',
        'title': '判断闰年',
        'stdin': '2024\n',
        'code': '''#include <stdio.h>
int main()
{
    int year;
    printf("请输入年份: ");
    scanf("%d", &year);
    if ((year % 4 == 0 && year % 100 != 0) || year % 400 == 0)
        printf("%d 年是闰年\\n", year);
    else
        printf("%d 年不是闰年\\n", year);
    return 0;
}''',
        'explain': '能被 4 整除且不能被 100 整除，或能被 400 整除的年份是闰年。',
    },
    {
        'pat': r'一元二次|方程的根',
        'title': '求一元二次方程的根',
        'stdin': '1 -3 2\n',
        'code': '''#include <stdio.h>
#include <math.h>
int main()
{
    double a, b, c, disc, x1, x2;
    printf("请输入系数 a b c: ");
    scanf("%lf%lf%lf", &a, &b, &c);
    disc = b * b - 4 * a * c;
    if (disc > 0)
    {
        x1 = (-b + sqrt(disc)) / (2 * a);
        x2 = (-b - sqrt(disc)) / (2 * a);
        printf("两个不等实根: x1=%.2f x2=%.2f\\n", x1, x2);
    }
    else if (disc == 0)
        printf("两个相等实根: x1=x2=%.2f\\n", -b / (2 * a));
    else
        printf("无实根（判别式小于0）\\n");
    return 0;
}''',
        'explain': '先求判别式 disc=b²-4ac，按其正负分三种情况求解。',
    },
    {
        'pat': r'大小写|字符转换',
        'title': '大小写字母转换',
        'code': '''#include <stdio.h>
int main()
{
    char ch;
    printf("请输入一个字母: ");
    ch = getchar();
    if (ch >= 'a' && ch <= 'z')
        printf("转换后: %c\\n", ch - 32);
    else if (ch >= 'A' && ch <= 'Z')
        printf("转换后: %c\\n", ch + 32);
    else
        printf("不是字母\\n");
    return 0;
}''',
        'explain': '利用 ASCII 码差值 32 实现大小写转换。',
    },
    {
        'pat': r'求和|1到|累加|sum\s*=|级数',
        'title': '循环求和',
        'code': '''#include <stdio.h>
int main()
{
    int i, n = 100;
    long s = 0;
    for (i = 1; i <= n; i++)
        s += i;
    printf("1+2+...+%d = %ld\\n", n, s);
    return 0;
}''',
        'explain': '用 for 循环完成 1~n 的累加求和。',
    },
    {
        'pat': r'最大值|max|最小值|min',
        'title': '函数求若干数的最大值',
        'code': '''#include <stdio.h>
int mymax(int a, int b, int c)
{
    int m = a;
    if (b > m) m = b;
    if (c > m) m = c;
    return m;
}
int main()
{
    int x, y, z;
    printf("请输入三个整数: ");
    scanf("%d%d%d", &x, &y, &z);
    printf("最大值是 %d\\n", mymax(x, y, z));
    return 0;
}''',
        'stdin': '13 47 25\n',
        'explain': '把求最大值逻辑封装成函数 mymax，主函数输入数据并调用输出结果，体现函数的模块化作用。',
    },
    {
        'pat': r'阶乘|递归',
        'title': '递归求阶乘',
        'code': '''#include <stdio.h>
long fact(int n)
{
    if (n <= 1)
        return 1;
    return (long)n * fact(n - 1);
}
int main()
{
    int n;
    printf("请输入 n: ");
    scanf("%d", &n);
    printf("%d! = %ld\\n", n, fact(n));
    return 0;
}''',
        'stdin': '10\n',
        'explain': '递归函数 fact(n) = n * fact(n-1)，边界条件 n<=1 返回 1，体现递归调用与回溯过程。',
    },
    {
        'pat': r'斐波那|Fibonacci',
        'title': '递归与迭代输出斐波那契数列',
        'code': '''#include <stdio.h>
long fib(int n)
{
    if (n == 1 || n == 2)
        return 1;
    return fib(n - 1) + fib(n - 2);
}
int main()
{
    int i;
    for (i = 1; i <= 15; i++)
        printf("%ld ", fib(i));
    printf("\\n");
    return 0;
}''',
        'explain': '递归定义 fib(n)=fib(n-1)+fib(n-2)，输出前 15 项；也可用迭代法避免重复计算提高效率。',
    },
    {
        'pat': r'交换.*两个|传值|传址',
        'title': '传值与传址交换两个变量',
        'code': '''#include <stdio.h>
void swap_value(int a, int b)      /* 传值：无法交换实参 */
{
    int t = a; a = b; b = t;
}
void swap_addr(int *a, int *b)     /* 传址：真正交换实参 */
{
    int t = *a; *a = *b; *b = t;
}
int main()
{
    int x = 3, y = 5;
    swap_value(x, y);
    printf("传值调用后:   x=%d y=%d\\n", x, y);
    swap_addr(&x, &y);
    printf("传址调用后:   x=%d y=%d\\n", x, y);
    return 0;
}''',
        'explain': '对比两种参数传递方式：传值只交换形参副本，传址通过指针修改实参，说明函数参数的本质是值传递。',
    },
    {
        'pat': r'指针.*数组|数组.*指针|指针遍历',
        'title': '用指针遍历一维数组',
        'code': '''#include <stdio.h>
int main()
{
    int a[5] = {10, 20, 30, 40, 50};
    int *p, i, sum = 0;
    for (p = a; p < a + 5; p++)
    {
        printf("%d ", *p);
        sum += *p;
    }
    printf("\\n数组元素之和 = %d\\n", sum);
    return 0;
}''',
        'explain': '数组名即首元素地址，p++ 按元素大小步进，*p 访问元素，体现指针与数组的等价关系。',
    },
    {
        'pat': r'字符串.*长度|strlen|字符串.*逆|回文',
        'title': '用指针求字符串长度',
        'code': '''#include <stdio.h>
int my_strlen(const char *s)
{
    const char *p = s;
    while (*p != '\\0')
        p++;
    return (int)(p - s);
}
int main()
{
    char str[100];
    printf("请输入字符串: ");
    scanf("%s", str);
    printf("长度 = %d\\n", my_strlen(str));
    return 0;
}''',
        'stdin': 'hello_nuist\n',
        'explain': '指针 p 从串首走到 \'\\0\'，指针差值即字符串长度，模拟标准库 strlen 的实现。',
    },
    {
        'pat': r'结构体.*排序|按.*(成绩|分数).*排序',
        'title': '结构体数组按成绩排序',
        'code': '''#include <stdio.h>
struct Student
{
    char name[20];
    int  score;
};
int main()
{
    struct Student s[5] = {
        {"zhang", 82}, {"wang", 91}, {"li", 76},
        {"zhao", 88}, {"chen", 95}};
    int i, j;
    struct Student t;
    for (i = 0; i < 4; i++)
        for (j = 0; j < 4 - i; j++)
            if (s[j].score < s[j + 1].score)
            {
                t = s[j]; s[j] = s[j + 1]; s[j + 1] = t;
            }
    printf("按成绩从高到低:\\n");
    for (i = 0; i < 5; i++)
        printf("%-8s %d\\n", s[i].name, s[i].score);
    return 0;
}''',
        'explain': '定义 struct Student，用冒泡排序按 score 降序整体交换结构体变量，输出排名表。',
    },
    {
        'pat': r'结构体|学生|共用体|union',
        'title': '结构体定义与学生信息管理',
        'code': '''#include <stdio.h>
struct Student
{
    int  num;
    char name[20];
    int  score;
};
int main()
{
    struct Student s1 = {20261305001, "zhongheng", 92};
    struct Student s[3];
    int i;
    s[0].num = 20261305002;
    sprintf(s[0].name, "chen");
    s[0].score = 85;
    s[1] = s1;                    /* 结构体变量可以整体赋值 */
    printf("%-12d %-10s %d\\n", s[0].num, s[0].name, s[0].score);
    printf("%-12d %-10s %d\\n", s[1].num, s[1].name, s[1].score);
    return 0;
}''',
        'explain': '演示结构体类型的定义、初始化、成员访问与整体赋值。',
    },
    {
        'pat': r'文件|fopen|fwrite',
        'title': '文件读写',
        'code': '''#include <stdio.h>
int main()
{
    FILE *fp;
    int i;
    fp = fopen("data.txt", "w");
    if (fp == NULL)
    {
        printf("文件打开失败\\n");
        return 1;
    }
    for (i = 1; i <= 5; i++)
        fprintf(fp, "%d ", i * i);
    fclose(fp);
    fp = fopen("data.txt", "r");
    while (1)
    {
        int x;
        fscanf(fp, "%d", &x);
        if (feof(fp)) break;
        printf("%d ", x);
    }
    fclose(fp);
    printf("\\n");
    return 0;
}''',
        'explain': '用 fprintf 写文件、fscanf+feof 读文件，练习文件的基本操作流程。',
    },
    {
        'pat': r'链表',
        'title': '单链表建立与遍历',
        'code': '''#include <stdio.h>
#include <stdlib.h>
struct Node
{
    int data;
    struct Node *next;
};
int main()
{
    struct Node *head = NULL, *p, *tail = NULL;
    int i;
    for (i = 1; i <= 5; i++)
    {
        p = (struct Node *)malloc(sizeof(struct Node));
        p->data = i * 10;
        p->next = NULL;
        if (head == NULL) head = p;
        else tail->next = p;
        tail = p;
    }
    for (p = head; p != NULL; p = p->next)
        printf("%d ", p->data);
    printf("\\n");
    return 0;
}''',
        'explain': '动态 malloc 建立单链表，尾插法保持顺序，遍历输出各结点数据。',
    },
]


def match_c_code(task_text):
    """按任务描述匹配代码模板，返回 dict 或 None。"""
    t = task_text.replace('　', '').replace(' ', '')
    for item in C_PATTERNS:
        if re.search(item['pat'], t):
            return item
    return None


# =====================================================================
# C 语言：各实验"分析与讨论"文案（参考南信大报告的实际写法）
# =====================================================================

C_ANALYSIS = {
    '程序控制结构': [
        '关于分支结构（if 与 switch）的对比思考',
        '在完成"成绩等级转换"任务时，我分别使用了 if-else 和 switch 语句，发现：',
        '• if-else 结构更擅长处理范围判断，逻辑直观；switch 结构只适合等值判断，需要先对成绩整除（score/10）把分数段映射为整数，且满分 100 要注意落在 case 10 的问题。',
        '• 健壮性反思：实验要求判断成绩的合法性（>100 或 <0），这让我认识到输入数据的合法性校验必不可少，否则程序会出现非预期的输出。',
        '关于整数位操作与循环控制的思考',
        '在完成"提取偶数数码重组新数"任务时：核心算法是用 %10 取最低位、/10 丢最低位，配合权值变量 pos 从低位向高位遍历；只有当提取到偶数数码时才累加 pos *= 10，这保证了"原高位仍在高位"。',
        '关于嵌套循环与算法效率的思考（易错点反思）',
        '编写"101~200 之间的素数个数"程序时，深刻体会到 break 语句和大括号 {} 的重要性：漏写大括号时 break 会无条件执行，导致内层循环提前退出、结果严重错误。效率上，外循环 i+=2 跳过偶数使次数减半，内循环只试除到 sqrt(i) 又进一步提高效率。',
        '关于二维数组与图形输出的思考（杨辉三角）',
        '通过状态转移方程 a[i][j] = a[i-1][j-1] + a[i-1][j] 即可生成每一行数据；打印时用 %6d 控制宽度才能排出美观的金字塔形状，这说明输出排版也是程序设计的重要一环。',
    ],
    '数组及其应用': [
        '关于数组下标越界的思考',
        '第（1）题的程序把 num[5]={1,2,3,4,5} 的五个元素全部输出后仍继续输出 num[5]，得到了一个随机值。这说明 C 编译器不检查下标越界，a[i] 只是按"首地址+i*元素大小"取内存，越界读写属于未定义行为，实际编程必须保证 0 <= i < 数组长度。',
        '关于排序算法测试的思考',
        '为冒泡排序设计测试用例时，我选取了正序、逆序、含重复元素、含负数、只有一个元素等边界情况。逆序输入时交换次数最多（n(n-1)/2 次），这也提示我可以加入"某趟无交换则提前结束"的优化标志位。',
        '关于二维数组存储方式的思考',
        '打印 3×5 数组各元素地址后可以看到：地址按行优先顺序连续递增，每行 5 个元素（每个 int 占 4 字节），行末元素地址加 4 就是下一行首元素地址。这验证了"二维数组按行存储"的结论，也解释了为什么用指针按 a[0]+i 的方式可以线性遍历整个二维数组。',
    ],
    '函数及其应用': [
        '关于函数模块化的思考',
        '把求最大值、判断素数等逻辑封装成函数后，主函数变得简洁清晰。函数是"做一件事"的独立单元，参数是输入、返回值是输出，这种划分让代码可以复用、也更容易定位错误。',
        '关于形参与实参的思考',
        '实验中对比了传值调用与传址调用：传值时形参是实参的副本，函数内修改形参不影响实参；需要函数修改外部变量时必须传地址（指针）。理解这一点后就不会再犯"为什么 swap 没有生效"的错误。',
        '关于递归的思考',
        '递归函数结构简洁（如求阶乘、斐波那契），但每次调用都要保存现场，开销较大；fib 的朴素递归存在大量重复计算，可用迭代或记忆化改进。递归的关键是找到递推关系并写清楚边界条件，否则会栈溢出。',
    ],
    '指针及其应用': [
        '关于指针概念的思考',
        '指针就是"存放地址的变量"。*p 是按 p 中的地址去访问内存，p++ 在数组场景下按元素大小步进。理解"指针的类型决定步长和解释方式"是本章的关键。',
        '关于指针与数组关系的思考',
        'a[i]、*(a+i)、p[i]、*(p+i) 四种写法等价，说明数组下标访问本质上是指针运算。但数组名是地址常量，不能 a++，而指针变量可以，两者的区别要牢记。',
        '关于常见错误的思考',
        '野指针（未初始化就使用）、返回局部变量地址、free 后继续使用等都是指针的经典错误。实验中我坚持"定义即初始化、使用前判空"的习惯，显著减少了程序崩溃。',
    ],
    '结构体及其应用': [
        '关于结构体数据组织的思考',
        '结构体把不同类型的成员组合成一个整体，让"一个学生"这种现实对象可以直接建模。结构体变量可以整体赋值、整体作函数参数，比逐个成员传递方便得多。',
        '关于结构体数组的思考',
        '结构体数组配合排序算法即可实现成绩排名等管理功能，成员访问 s[j].score 的写法与普通数组排序完全一致，体现了"数据结构 + 算法"的组织方式。',
        '关于内存对齐的体会',
        '用 sizeof 观察结构体大小时发现它常大于各成员大小之和，这是编译器为了访问效率做了字节对齐。成员按大小排序可以减少 padding，这是实际工程中值得注意的细节。',
    ],
    '语法基础': [
        '关于数据类型与运算的思考',
        'C 语言的 int/float/char 占用字节数不同，混用时会发生隐式类型转换，整数除法 5/2 的结果是 2 而不是 2.5，这类细节最容易出错，写代码时要显式转换或使用浮点常量。',
        '关于输入输出格式的思考',
        'scanf 必须传地址（&a），格式符与变量类型必须一致，否则会读到脏数据；printf 的 %d/%f/%c/%s 各有用途，%m.nf 可以控制小数位数，格式化输出让结果更规范。',
        '关于运算符优先级的思考',
        '赋值号 = 与相等判断 == 的混淆是初学者最常见的错误，实验中我养成了"把常量写在左边（3 == x）"的习惯，能有效避免误写。',
    ],
    '_default': [
        '本次实验按题目顺序完成了全部任务的编程与调试。',
        '调试过程中遇到的主要问题是格式符与变量类型不匹配、以及循环边界条件写错，通过单步跟踪和插入 printf 观察中间变量解决。',
        '通过本次实验，我进一步熟悉了从分析问题、编写代码、编译排错到验证结果的完整流程，对所学知识的理解更加扎实。',
    ],
}


def c_analysis_paragraphs(exp_name):
    for k, paras in C_ANALYSIS.items():
        if k != '_default' and k in exp_name:
            return paras
    return C_ANALYSIS['_default']


# =====================================================================
# 工程制图（AutoCAD 上机）
# =====================================================================

DRAWING_STEPS_POOL = {
    '图层': ('设定图层', '打开图层特性管理器，新建"粗实线、细点画线、细实线、尺寸标注"等图层，并设置对应颜色与线型（点画线用 CENTER、虚线用 DASHED）。'),
    '中心线': ('绘制对称中心线', '切换到细点画线图层，用直线（L）命令绘制水平和竖直对称中心线，确定图形基准。'),
    '圆': ('绘制同心圆', '用圆（C）命令以中心线交点为圆心，按给定直径依次绘制各同心圆，注意随时切换图层。'),
    '阵列': ('环形阵列均布结构', '用环形阵列（ARRAYPOLAR）选取公共圆心为中心，项目数按题目要求设置，完成均布小圆/槽的绘制。'),
    '修剪': ('修剪多余图线', '用修剪（TR）命令删去多余线段，必要时配合打断（BR）、倒角（CHA）等修改命令。'),
    '偏移': ('偏移定位线', '用偏移（O）命令按给定距离复制中心线得到定位线，再切换到粗实线图层。'),
    '标注': ('尺寸标注', '切换到标注图层，设置标注样式（ISO），用线性（DLI）、直径（DDI）、半径（DRA）等命令完成尺寸标注。'),
    '保存': ('保存与出图', '核对图形无误后保存 dwg 文件，并用布局打印输出 PDF 便于插入报告。'),
}

DRAWING_EXPERIMENTS = [
    {
        'pat': r'平面图形|修改与编辑|第二次',
        'name': '平面图形的绘制、修改与编辑',
        'purpose_hint': '对象选取方法、常用修改命令、对象捕捉、绘制编辑修改简单二维图形',
        'steps': ['图层', '中心线', '圆', '阵列', '修剪', '偏移', '标注', '保存'],
        'figures': ('图一', '图二'),
    },
    {
        'pat': r'基本操作|界面|直线|第一次|初始',
        'name': 'AutoCAD 基本操作与平面图形绘制',
        'purpose_hint': '熟悉 AutoCAD 界面与命令输入方式、掌握直线/圆等基本绘图命令、学会图层设置',
        'steps': ['图层', '中心线', '圆', '修剪', '标注', '保存'],
        'figures': ('图一',),
    },
    {
        'pat': r'三视图|组合体',
        'name': '组合体三视图的绘制',
        'purpose_hint': '运用投影规律绘制组合体三视图、掌握对象捕捉与极轴追踪辅助绘图',
        'steps': ['图层', '中心线', '偏移', '修剪', '标注', '保存'],
        'figures': ('图一',),
    },
]


def match_drawing_exp(text):
    t = text.replace(' ', '')
    for item in DRAWING_EXPERIMENTS:
        if re.search(item['pat'], t):
            return item
    return DRAWING_EXPERIMENTS[0]


DRAWING_RESULT_NOTE = 'dwg 文件提交至学习通，提交时间等老师统一通知。'


# =====================================================================
# 课程识别
# =====================================================================

COURSE_ALIASES = {
    'c': ('c语言', 'c 程序设计', 'c语言程序设计', '程序设计'),
    'drawing': ('工程制图', 'autocad', 'cad', '制图'),
}


def guess_course(text, exp_name=''):
    t = (text + ' ' + exp_name).lower()
    for key, words in COURSE_ALIASES.items():
        for w in words:
            if w in t:
                return key
    return 'c'


def drawing_step_items(step_keys):
    return [DRAWING_STEPS_POOL[k] for k in step_keys if k in DRAWING_STEPS_POOL]
