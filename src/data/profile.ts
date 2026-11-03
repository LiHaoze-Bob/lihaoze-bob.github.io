export const profile = {
  name: 'Haoze Li', nickname: 'sychostar',
  email: 'haozeli2025@gmail.com', github: 'https://github.com/LiHaoze-Bob',
  bilibili: 'https://space.bilibili.com/2118021600', zhihu: 'https://www.zhihu.com/people/sychostar',
  avatar: '/assets/images/avatar.png',
  school: { name: 'Zhejiang University', url: 'https://www.zju.edu.cn/' },
  education: [
    { school: 'Zhejiang University', program: 'Computer Science and Technology · Undergraduate', period: 'Jul 2025 – Present', url: 'https://www.zju.edu.cn/', image: 'zju.png' },
    { school: 'Hangzhou High School, Zhejiang', program: 'High school', period: 'Sep 2022 – Jul 2025', url: 'http://www.hanggao.net/', image: 'hanggao.jpg' }
  ]
}

interface Project {
  id: string
  name: string
  summary: string
  paragraphs: string[]
  code: string
}

export const projects: Project[] = [
  {
    id: 'lingxiglove', name: 'LingxiGlove',
    summary: 'A gesture-to-speech glove prototype exploring how hand gestures can become spoken words.',
    paragraphs: [
      'LingxiGlove explores a path from hand gestures to spoken output. It combines bend sensors and an inertial sensor with an ESP32-S3, connecting gesture recognition on the device to a cloud speech service.',
      'The prototype focuses on a small set of rule-based gestures and a speech-output loop. The repository includes firmware, wiring and setup documentation, and host-side tests. Learned recognition and two-hand synchronization are further development directions, rather than capabilities claimed for the current prototype.'
    ],
    code: 'https://github.com/LiHaoze-Bob/LingxiGlove'
  },
  {
    id: 'zju-sports-hub', name: 'ZJU Sports Hub',
    summary: 'A website that brings Zhejiang University’s campus sports events together in one place.',
    paragraphs: [
      'Campus sports announcements are spread across different student organizations. ZJU Sports Hub brings that information into a browsable website, with event details and filters for campus and category.',
      'The pipeline collects posts through RSS and uses an LLM to turn announcements into structured event data. A Next.js frontend reads the resulting data to present the events. The repository documents collection, parsing, deduplication, and deployment; it also includes a data snapshot that can be viewed without connecting the collection services.'
    ],
    code: 'https://github.com/LiHaoze-Bob/ZJU-Sports-Hub'
  }
]
